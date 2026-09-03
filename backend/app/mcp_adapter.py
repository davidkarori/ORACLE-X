import hashlib
import json
import time
import uuid
from typing import Any

import httpx

from .config import Settings
from .domain import AgentRole, McpToolCall
from .integrations import IntegrationError


class AlpacaMcpAdapter:
    READ_ONLY_TOOLS = frozenset(
        {
            "get_account_info",
            "get_asset",
            "get_option_contracts",
            "get_clock",
            "get_stock_snapshot",
            "get_stock_latest_quote",
            "get_option_latest_quote",
            "get_option_snapshot",
            "get_option_chain",
            "get_news",
        }
    )
    FORBIDDEN_TOOLS = frozenset(
        {
            "place_stock_order",
            "place_crypto_order",
            "place_option_order",
            "replace_order_by_id",
            "cancel_order_by_id",
            "cancel_all_orders",
            "close_position",
            "close_all_positions",
            "exercise_options_position",
            "do_not_exercise_options_position",
            "update_account_config",
        }
    )

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def research(self, symbol: str) -> tuple[list[McpToolCall], dict[str, Any]]:
        requests = [
            ("get_stock_snapshot", AgentRole.ATHENA, {"symbol": symbol}),
            ("get_option_chain", AgentRole.ATHENA, {"underlying_symbol": symbol}),
            ("get_news", AgentRole.HADES, {"symbols": symbol, "limit": 5}),
        ]
        calls: list[McpToolCall] = []
        context: dict[str, Any] = {}
        for tool_name, requester, arguments in requests:
            call, result = await self.call(tool_name, requester, arguments)
            calls.append(call)
            context[tool_name] = result
        return calls, context

    async def call(
        self,
        tool_name: str,
        requesting_agent: AgentRole,
        arguments: dict[str, Any],
    ) -> tuple[McpToolCall, Any]:
        if tool_name in self.FORBIDDEN_TOOLS or tool_name not in self.READ_ONLY_TOOLS:
            raise IntegrationError(f"MCP tool is not allowlisted for read-only use: {tool_name}")
        started = time.perf_counter()
        if not self.settings.mcp_server_url:
            result: Any = {"mode": "fixture", "tool": tool_name, "symbol": next(iter(arguments.values()), None)}
        else:
            headers = {
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            }
            try:
                async with httpx.AsyncClient(timeout=self.settings.mcp_timeout_seconds) as client:
                    initialize = await client.post(
                        self.settings.mcp_server_url,
                        headers=headers,
                        json={
                            "jsonrpc": "2.0",
                            "id": uuid.uuid4().hex,
                            "method": "initialize",
                            "params": {
                                "protocolVersion": "2025-03-26",
                                "capabilities": {},
                                "clientInfo": {"name": "oracle-x", "version": "0.1.0"},
                            },
                        },
                    )
                    initialize.raise_for_status()
                    session_id = initialize.headers.get("mcp-session-id")
                    body = self._response_body(initialize)
                    if body.get("error"):
                        raise IntegrationError(f"MCP initialization failed: {body['error'].get('message', 'unknown error')}")
                    session_headers = {**headers, **({"Mcp-Session-Id": session_id} if session_id else {})}
                    ready = await client.post(
                        self.settings.mcp_server_url,
                        headers=session_headers,
                        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                    )
                    ready.raise_for_status()
                    response = await client.post(
                        self.settings.mcp_server_url,
                        headers=session_headers,
                        json={
                            "jsonrpc": "2.0",
                            "id": uuid.uuid4().hex,
                            "method": "tools/call",
                            "params": {"name": tool_name, "arguments": arguments},
                        },
                    )
                    response.raise_for_status()
                    body = self._response_body(response)
                if body.get("error"):
                    raise IntegrationError(f"MCP {tool_name} failed: {body['error'].get('message', 'unknown error')}")
                result = body.get("result", {})
            except (httpx.HTTPError, IntegrationError, ValueError, TypeError) as exc:
                latency = int((time.perf_counter() - started) * 1000)
                call = McpToolCall(
                    id=uuid.uuid4().hex,
                    tool_name=tool_name,
                    requesting_agent=requesting_agent,
                    arguments=arguments,
                    result_metadata={"transport": "streamable-http"},
                    latency_ms=latency,
                    success=False,
                    error=str(exc),
                )
                return call, {"error": "MCP_READ_FAILED"}
        encoded = json.dumps(result, default=str, sort_keys=True).encode()
        metadata = {
            "transport": "fixture" if not self.settings.mcp_server_url else "streamable-http",
            "sha256": hashlib.sha256(encoded).hexdigest(),
            "bytes": len(encoded),
            "content_type": type(result).__name__,
        }
        call = McpToolCall(
            id=uuid.uuid4().hex,
            tool_name=tool_name,
            requesting_agent=requesting_agent,
            arguments=arguments,
            result_metadata=metadata,
            latency_ms=int((time.perf_counter() - started) * 1000),
            success=True,
        )
        return call, result

    @staticmethod
    def _response_body(response: httpx.Response) -> dict[str, Any]:
        content_type = response.headers.get("content-type", "")
        if "text/event-stream" not in content_type:
            body = response.json()
            if not isinstance(body, dict):
                raise IntegrationError("MCP response was not a JSON object")
            return body
        for line in reversed(response.text.splitlines()):
            if line.startswith("data:"):
                body = json.loads(line.removeprefix("data:").strip())
                if not isinstance(body, dict):
                    raise IntegrationError("MCP event data was not a JSON object")
                return body
        raise IntegrationError("MCP event stream did not contain a data event")

$ErrorActionPreference = 'Stop'

if (-not (Get-Command alpaca -ErrorAction SilentlyContinue)) {
    throw 'Alpaca CLI is not installed. See https://github.com/alpacahq/cli.'
}

if (-not $env:ALPACA_API_KEY -or -not $env:ALPACA_SECRET_KEY) {
    throw 'Set ALPACA_API_KEY and ALPACA_SECRET_KEY in the current shell.'
}

if ($env:ALPACA_LIVE_TRADE -eq 'true') {
    throw 'Refusing to run: ALPACA_LIVE_TRADE must not be true.'
}

alpaca doctor
alpaca account get --quiet
alpaca clock --quiet
alpaca data bars --symbol SPY --start 2026-08-28 --timeframe 1Day --quiet

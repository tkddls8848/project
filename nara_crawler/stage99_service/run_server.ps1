Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

$ProjectRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
Set-Location -LiteralPath $ProjectRoot.Path
$LogPath = Join-Path $PSScriptRoot "uvicorn.combined.log"

"starting stage99_service" | Set-Content -LiteralPath $LogPath -Encoding UTF8
$Command = "python -m uvicorn stage99_service.main:app --host 127.0.0.1 --port 8000 --log-level info >> `"$LogPath`" 2>&1"
cmd.exe /c $Command

# Nara local launch: search(8000) + combiner(8003) + dashboard(5173)
# Usage: .\start-all.ps1 [-ApidataDir <path>]
#
# NOTE: keep this file ASCII-only. Windows PowerShell 5.1 reads BOM-less .ps1
# files as the system code page (cp949 on Korean Windows), which corrupts any
# non-ASCII literal (e.g. the Korean directory names). We therefore resolve the
# project folders by ASCII prefix instead of hardcoding their Korean names.
param(
  [string]$ApidataDir = (Join-Path $PSScriptRoot 'nara_storage\openapi_new')
)

function Resolve-ProjectDir([string]$prefix) {
  $dir = Get-ChildItem -LiteralPath $PSScriptRoot -Directory -Filter "$prefix*" |
    Select-Object -First 1
  if ($null -eq $dir) {
    Write-Warning "Project folder not found: $prefix* under $PSScriptRoot"
    return $null
  }
  return $dir.FullName
}

if (-not (Test-Path -LiteralPath $ApidataDir)) {
  Write-Warning "API document directory not found: $ApidataDir"
  Write-Warning "Search/catalog will start empty. Run nara_crawler to fill nara_storage, or pass -ApidataDir."
}

$search    = Resolve-ProjectDir 'nara_search'
$combiner  = Resolve-ProjectDir 'nara_combiner'
$dashboard = Resolve-ProjectDir 'nara_dashboard'

if ($search) {
  Start-Process powershell -WorkingDirectory $search -ArgumentList '-NoExit', '-Command',
    "`$env:PYTHONIOENCODING='utf-8'; `$env:NARA_SEARCH_APIDATA_DIR='$ApidataDir'; python -m uvicorn backend.main:app --port 8000"
}
if ($combiner) {
  Start-Process powershell -WorkingDirectory $combiner -ArgumentList '-NoExit', '-Command',
    "`$env:PYTHONIOENCODING='utf-8'; `$env:NARA_DATA_DIR='$ApidataDir'; python .\app\main.py"
}
if ($dashboard) {
  Start-Process powershell -WorkingDirectory $dashboard -ArgumentList '-NoExit', '-Command', 'npm run dev'
}

Write-Host ''
Write-Host 'Launched (check logs in each window):'
Write-Host '  search     http://127.0.0.1:8000/health'
Write-Host '  combiner   http://127.0.0.1:8003/health'
Write-Host '  dashboard  http://localhost:5173'

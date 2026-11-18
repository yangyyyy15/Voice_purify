param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Create .venv first; see docs/windows-runtime.md' }
if (-not (Test-Path 'frontend\dist\index.html')) { throw 'Build frontend first: cd frontend; npm ci; npm run build' }
$env:PYTHONIOENCODING = 'utf-8'
Write-Host "Review UI: http://127.0.0.1:$Port"
& $python -m uvicorn backend.api:app --host 127.0.0.1 --port $Port
exit $LASTEXITCODE

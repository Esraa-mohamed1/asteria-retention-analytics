#!/usr/bin/env pwsh
# coke.ps1 — project shortcuts for Windows PowerShell
# Usage: .\coke.ps1 [command]
#   .\coke.ps1          → full pipeline (fixtures, no network)
#   .\coke.ps1 live     → pipeline with live Eurostat/World Bank APIs
#   .\coke.ps1 test     → run test suite only
#   .\coke.ps1 dash     → rebuild dashboard HTML only
#   .\coke.ps1 install  → pip install in editable mode
#   .\coke.ps1 open     → open dashboard in default browser

param([string]$cmd = "run")

$ErrorActionPreference = "Stop"
$python = "python"

function Run-Pipeline($source) {
    Write-Host "▶ Running pipeline (source=$source) ..." -ForegroundColor Cyan
    & $python -c "import sys; sys.path.insert(0,'src'); from asteria_retention.cli import main; import sys; sys.argv=['cli','run','--source','$source']; main()"
}

switch ($cmd) {
    "install" {
        Write-Host "▶ Installing dependencies ..." -ForegroundColor Cyan
        & $python -m pip install -e ".[dev]" --quiet
        Write-Host "✓ Done" -ForegroundColor Green
    }
    "live" {
        Run-Pipeline "live"
    }
    "test" {
        Write-Host "▶ Running tests ..." -ForegroundColor Cyan
        & $python -m pytest tests/ -v
    }
    "dash" {
        Write-Host "▶ Rebuilding dashboard ..." -ForegroundColor Cyan
        & $python -c "import sys; sys.path.insert(0,'src'); from asteria_retention.cli import main; import sys; sys.argv=['cli','build-dashboard']; main()"
        Write-Host "✓ dashboard/index.html rebuilt" -ForegroundColor Green
    }
    "open" {
        $path = (Resolve-Path "dashboard\index.html").Path
        Write-Host "▶ Opening $path" -ForegroundColor Cyan
        Start-Process $path
    }
    default {
        Run-Pipeline "fixtures"
    }
}

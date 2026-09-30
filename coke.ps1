#!/usr/bin/env pwsh
# coke.ps1 -- project shortcuts for Windows PowerShell
# Usage: .\coke.ps1 [command]
#   .\coke.ps1          -> full pipeline (fixtures, no network)
#   .\coke.ps1 live     -> pipeline with live Eurostat/World Bank APIs
#   .\coke.ps1 test     -> run test suite only
#   .\coke.ps1 dash     -> rebuild dashboard HTML only
#   .\coke.ps1 install  -> pip install in editable mode
#   .\coke.ps1 open     -> open dashboard in default browser

param([string]$cmd = "run")

$ErrorActionPreference = "Stop"
$python = "python"

switch ($cmd) {
    "install" {
        Write-Host "Installing dependencies ..." -ForegroundColor Cyan
        & $python -m pip install -e ".[dev]" --quiet
        Write-Host "Done." -ForegroundColor Green
    }
    "live" {
        Write-Host "Running pipeline with live APIs ..." -ForegroundColor Cyan
        & $python -m asteria_retention run --source live
    }
    "test" {
        Write-Host "Running tests ..." -ForegroundColor Cyan
        & $python -m pytest tests/ -v
    }
    "dash" {
        Write-Host "Rebuilding dashboard ..." -ForegroundColor Cyan
        & $python -m asteria_retention build-dashboard
        Write-Host "dashboard/index.html rebuilt." -ForegroundColor Green
    }
    "open" {
        $htmlPath = (Resolve-Path "dashboard\index.html").Path
        Write-Host "Opening $htmlPath" -ForegroundColor Cyan
        Start-Process $htmlPath
    }
    default {
        Write-Host "Running pipeline with fixtures ..." -ForegroundColor Cyan
        & $python -m asteria_retention run --source fixtures
    }
}

#!/usr/bin/env pwsh
# coke.ps1 -- project shortcuts for Windows PowerShell
# Usage: .\coke.ps1 [command]
#   .\coke.ps1          -> full pipeline (fixtures, no network)
#   .\coke.ps1 live     -> pipeline with live Eurostat/World Bank APIs
#   .\coke.ps1 test     -> run test suite only
#   .\coke.ps1 dash     -> rebuild dashboard HTML only
#   .\coke.ps1 install  -> pip install in editable mode
#   .\coke.ps1 open     -> open dashboard in default browser
#   .\coke.ps1 doctor   -> test live API connectivity per indicator
#   .\coke.ps1 verify   -> verify data files against manifest checksums

param([string]$cmd = "run")

$ErrorActionPreference = "Stop"
$python = "python"

# Ensure src is on PYTHONPATH so commands run reliably
$srcPath = Join-Path $PSScriptRoot "src"
if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$srcPath;$env:PYTHONPATH"
} else {
    $env:PYTHONPATH = $srcPath
}

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
        $htmlPath = Join-Path $PSScriptRoot "dashboard\index.html"
        if (-not (Test-Path $htmlPath)) {
            Write-Host "Dashboard not found. Building dashboard first ..." -ForegroundColor Yellow
            & $python -m asteria_retention build-dashboard
        }
        Write-Host "Opening $htmlPath" -ForegroundColor Cyan
        Start-Process $htmlPath
    }
    "doctor" {
        Write-Host "Checking live API connectivity ..." -ForegroundColor Cyan
        & $python -m asteria_retention doctor
    }
    "verify" {
        Write-Host "Verifying data manifest checksums ..." -ForegroundColor Cyan
        & $python -m asteria_retention verify-data
    }
    default {
        Write-Host "Running pipeline with fixtures ..." -ForegroundColor Cyan
        & $python -m asteria_retention run --source fixtures
    }
}

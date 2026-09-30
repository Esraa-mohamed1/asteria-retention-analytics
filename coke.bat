@echo off
:: coke.bat -- project shortcuts (double-click or call from cmd)
:: Usage: coke          -> full pipeline (fixtures)
::        coke live     -> pipeline with live APIs
::        coke test     -> tests only
::        coke dash     -> rebuild dashboard
::        coke open     -> open dashboard in browser
::        coke install  -> pip install
::        coke doctor   -> check live API connectivity
::        coke verify   -> verify data manifest checksums

set PYTHONPATH=src;%PYTHONPATH%

set CMD=%1
if "%CMD%"=="" set CMD=run

if "%CMD%"=="install" (
    echo Installing dependencies...
    python -m pip install -e ".[dev]" --quiet
    echo Done.
    goto end
)

if "%CMD%"=="test" (
    echo Running tests...
    python -m pytest tests/ -v
    goto end
)

if "%CMD%"=="dash" (
    echo Rebuilding dashboard...
    python -m asteria_retention build-dashboard
    echo dashboard\index.html rebuilt.
    goto end
)

if "%CMD%"=="open" (
    if not exist "dashboard\index.html" (
        echo Dashboard not found. Building dashboard first...
        python -m asteria_retention build-dashboard
    )
    start "" "dashboard\index.html"
    goto end
)

if "%CMD%"=="live" (
    echo Running pipeline with live APIs...
    python -m asteria_retention run --source live
    goto end
)

if "%CMD%"=="doctor" (
    echo Running API health doctor...
    python -m asteria_retention doctor
    goto end
)

if "%CMD%"=="verify" (
    echo Verifying data manifest...
    python -m asteria_retention verify-data
    goto end
)

:: default: run with fixtures
echo Running pipeline (offline fixtures)...
python -m asteria_retention run --source fixtures

:end

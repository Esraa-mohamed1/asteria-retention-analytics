@echo off
:: coke.bat — project shortcuts (double-click or call from cmd)
:: Usage: coke          → full pipeline (fixtures)
::        coke live     → pipeline with live APIs
::        coke test     → tests only
::        coke dash     → rebuild dashboard
::        coke open     → open dashboard in browser
::        coke install  → pip install

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
    python -c "import sys; sys.path.insert(0,'src'); from asteria_retention.cli import main; sys.argv=['cli','build-dashboard']; main()"
    echo dashboard\index.html rebuilt.
    goto end
)

if "%CMD%"=="open" (
    start "" "dashboard\index.html"
    goto end
)

if "%CMD%"=="live" (
    echo Running pipeline with live APIs...
    python -c "import sys; sys.path.insert(0,'src'); from asteria_retention.cli import main; sys.argv=['cli','run','--source','live']; main()"
    goto end
)

:: default: run with fixtures
echo Running pipeline (offline fixtures)...
python -c "import sys; sys.path.insert(0,'src'); from asteria_retention.cli import main; sys.argv=['cli','run','--source','fixtures']; main()"

:end

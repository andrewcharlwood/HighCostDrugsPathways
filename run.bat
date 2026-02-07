@echo off
setlocal EnableDelayedExpansion

title HCD Patient Pathway Analysis
echo.
echo  ==========================================
echo   HCD Patient Pathway Analysis
echo   NHS High-Cost Drug Treatment Pathways
echo  ==========================================
echo.

:: -------------------------------------------------------
:: First run vs subsequent run
:: -------------------------------------------------------
if exist ".venv\Scripts\activate.bat" (
    echo  Ready to launch.
    goto :run_app
)

echo  First-time setup detected. This will:
echo    1. Install uv (Python package manager)
echo    2. Install Python 3.12 and dependencies
echo    3. Build and start the application
echo.
echo  Requires internet access. May take 3-5 minutes.
echo.
pause

:: -------------------------------------------------------
:: Install uv if not available
:: -------------------------------------------------------
where uv >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo.
    echo [1/3] Installing uv...
    powershell -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"

    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
    set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"

    where uv >nul 2>&1
    if !ERRORLEVEL! neq 0 (
        echo.
        echo  ERROR: uv installation failed.
        echo  Try installing manually: https://docs.astral.sh/uv/getting-started/installation/
        echo  Then re-run this script.
        pause
        exit /b 1
    )
    echo  uv installed successfully.
) else (
    echo [1/3] uv already installed.
)

:: -------------------------------------------------------
:: Sync dependencies
:: -------------------------------------------------------
echo.
echo [2/3] Installing Python and dependencies...
echo  (First run only — please wait)
echo.

uv sync
if %ERRORLEVEL% neq 0 (
    echo.
    echo  ERROR: Dependency installation failed.
    echo  Check your internet connection and try again.
    pause
    exit /b 1
)

echo.
echo  Setup complete.

:: -------------------------------------------------------
:: Run application
:: -------------------------------------------------------
:run_app
echo.
echo [3/3] Starting application...
echo.
echo  App will open at: http://localhost:3000
echo  First launch builds the frontend (~60 seconds).
echo  Subsequent launches are fast.
echo.
echo  To stop: close this window or press Ctrl+C
echo  ==========================================
echo.

start "" cmd /c "timeout /t 8 /nobreak >nul && start http://localhost:3000"

uv run reflex run
if %ERRORLEVEL% neq 0 (
    echo.
    echo  Application exited with an error.
    echo  Try deleting .web\ and running again.
    echo.
    pause
)

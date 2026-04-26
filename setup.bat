@echo off

echo ==========================================
echo zeroos - Complete Setup
echo ==========================================
echo.

where uv >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Installing uv...
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    echo + uv installed
) else (
    echo + uv found
)

echo.
echo Removing old virtual environment...
if exist ".venv" (
    rmdir /s /q .venv
    echo + Old venv removed
)

echo.
echo Creating fresh virtual environment...
uv venv
echo + Virtual environment created

echo.
echo Installing dependencies...
uv sync

if %ERRORLEVEL% NEQ 0 (
    echo X Failed to install dependencies
    exit /b 1
)

echo.
echo Installing pre-commit hooks...
uv run pre-commit install >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo + Pre-commit hooks installed
) else (
    echo ! Warning: Failed to install pre-commit hooks
    echo   You can install them later with: uv run pre-commit install
)

echo.
echo ==========================================
echo + Setup complete!
echo ==========================================
echo.

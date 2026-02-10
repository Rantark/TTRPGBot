@echo off
echo ========================================
echo  TTRPGBot Auto-Updater (Windows)
echo ========================================
echo.

echo [1/4] Fetching latest changes from GitHub...
git fetch origin claude/dnd-discord-bot-e1Rh5
if errorlevel 1 (
    echo ERROR: Failed to fetch from GitHub
    echo Make sure you have git installed and internet connection
    exit /b 1
)

echo [2/4] Pulling latest code...
git pull origin claude/dnd-discord-bot-e1Rh5
if errorlevel 1 (
    echo ERROR: Failed to pull updates
    echo You may have local changes that conflict
    exit /b 1
)

echo [3/4] Installing/updating dependencies...
pip install -r requirements.txt --upgrade
if errorlevel 1 (
    echo WARNING: Failed to update dependencies
    echo The bot may still work with old packages
)

echo [4/4] Update complete!
echo.

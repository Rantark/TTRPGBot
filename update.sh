#!/bin/bash

echo "========================================"
echo " TTRPGBot Auto-Updater (Linux/Mac)"
echo "========================================"
echo ""

echo "[1/4] Fetching latest changes from GitHub..."
git fetch origin claude/dnd-discord-bot-e1Rh5
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to fetch from GitHub"
    echo "Make sure you have git installed and internet connection"
    exit 1
fi

echo "[2/4] Pulling latest code..."
git pull origin claude/dnd-discord-bot-e1Rh5
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to pull updates"
    echo "You may have local changes that conflict"
    exit 1
fi

echo "[3/4] Installing/updating dependencies..."
pip3 install -r requirements.txt --upgrade
if [ $? -ne 0 ]; then
    echo "WARNING: Failed to update dependencies"
    echo "The bot may still work with old packages"
fi

echo "[4/4] Update complete!"
echo ""

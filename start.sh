#!/bin/bash

echo "========================================"
echo " TTRPGBot - D&D 5e Discord Bot"
echo "========================================"
echo ""

# Mark wrapper as active
touch .wrapper_active

while true; do
    echo "[$(date)] Starting bot..."
    python3 -m bot.main
    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 42 ]; then
        echo ""
        echo "[$(date)] Bot requested restart..."
        echo "[$(date)] Restarting in 3 seconds..."
        sleep 3
        continue
    fi

    if [ $EXIT_CODE -eq 43 ]; then
        echo ""
        echo "[$(date)] Bot requested update..."
        echo "[$(date)] Running update script..."
        ./update.sh
        echo ""
        echo "[$(date)] Update complete, restarting..."
        sleep 3
        continue
    fi

    echo ""
    echo "[$(date)] Bot stopped normally."
    rm -f .wrapper_active
    break
done

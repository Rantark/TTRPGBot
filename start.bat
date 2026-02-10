@echo off
title TTRPGBot - D&D 5e Discord Bot
echo ========================================
echo  TTRPGBot - D&D 5e Discord Bot
echo ========================================
echo.

REM Mark wrapper as active
echo active > .wrapper_active

:start
echo [%date% %time%] Starting bot...
python -m bot.main

if errorlevel 43 (
    echo.
    echo [%date% %time%] Bot requested update...
    echo [%date% %time%] Running update script...
    call update.bat
    echo.
    echo [%date% %time%] Update complete, restarting...
    timeout /t 3 /nobreak >nul
    goto start
)

if errorlevel 42 (
    echo.
    echo [%date% %time%] Bot requested restart...
    echo [%date% %time%] Restarting in 3 seconds...
    timeout /t 3 /nobreak >nul
    goto start
)

echo.
echo [%date% %time%] Bot stopped normally.
del .wrapper_active
echo Press any key to exit...
pause >nul

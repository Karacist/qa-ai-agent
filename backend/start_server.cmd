@echo off
setlocal

cd /d "%~dp0\.."

echo Starting backend server...
echo.

python backend\server.py
echo.
echo Backend server exited.
pause

endlocal


@echo off
chcp 65001 > nul
echo ========================================================
echo    Windows Activity Tracker - Bấm chạy là đẩy ngay Railway
echo ========================================================
echo.

set SERVER_URL=https://spy-production-8aaa.up.railway.app
set API_TOKEN=hoanganh

if exist "server_url.txt" (
    set /p SERVER_URL=<server_url.txt
)

echo [*] Đang kích hoạt và đẩy ngay lập tức hoạt động máy tính lên Railway...
echo Server mục tiêu: %SERVER_URL%
echo.

python -m client.cli run --raw-mode --server-url "%SERVER_URL%" --api-token "%API_TOKEN%"
if %errorlevel% neq 0 (
    echo [*] Chạy với Standalone Client (Zero-Dependency)...
    python standalone_client.py --raw-mode --server-url "%SERVER_URL%" --api-token "%API_TOKEN%"
)
pause

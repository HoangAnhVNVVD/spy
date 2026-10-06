@echo off
chcp 65001 > nul
echo ========================================================
echo    Windows Activity Tracker - Bấm chạy là đẩy ngay Railway
echo ========================================================
echo.

if exist "server_url.txt" (
    set /p SERVER_URL=<server_url.txt
) else (
    echo Vui lòng dán link domain Railway của bạn (ví dụ: https://spy-production.up.railway.app):
    set /p SERVER_URL="Link Railway: "
    echo !SERVER_URL!
    echo %SERVER_URL%>server_url.txt
)

if "%SERVER_URL%"=="" set SERVER_URL=http://localhost:8000
set API_TOKEN=default-secret-token

echo [*] Đang chụp và đẩy ngay lập tức hoạt động máy tính lên Railway...
echo Server mục tiêu: %SERVER_URL%
echo.

python -m client.cli run --raw-mode --server-url "%SERVER_URL%" --api-token "%API_TOKEN%"
if %errorlevel% neq 0 (
    echo [*] Chạy với Standalone Client (Zero-Dependency)...
    python standalone_client.py --raw-mode --server-url "%SERVER_URL%" --api-token "%API_TOKEN%"
)
pause

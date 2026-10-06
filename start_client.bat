@echo off
chcp 65001 > nul
echo ========================================================
echo    Khởi động Windows Activity Tracker Client
echo ========================================================

:: Cấu hình địa chỉ server Railway và token của bạn ở đây:
set SERVER_URL=http://localhost:8000
set API_TOKEN=default-secret-token

:: Nếu bạn đã có domain Railway, hãy sửa dòng trên thành:
:: set SERVER_URL=https://<your-app>.up.railway.app
:: set API_TOKEN=your-token-here

echo [*] Đang chạy Tracker ở chế độ Raw Mode...
echo Server mục tiêu: %SERVER_URL%
echo Nhấn Ctrl+C để dừng hoạt động nếu muốn.
echo.

python -m client.cli run --raw-mode --server-url "%SERVER_URL%" --api-token "%API_TOKEN%"
pause

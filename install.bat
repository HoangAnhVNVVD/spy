@echo off
chcp 65001 > nul
echo ========================================================
echo    Cài đặt Windows Activity Tracker trên máy mới
echo ========================================================
echo.

python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [LỖI] Máy tính chưa cài đặt Python!
    echo Vui lòng tải và cài đặt Python từ https://www.python.org/downloads/
    echo Lưu ý: Hãy tích chọn "Add python.exe to PATH" khi cài đặt.
    pause
    exit /b 1
)

echo [*] Đang cài đặt các thư viện cần thiết...
pip install -r requirements.txt

if %errorlevel% equ 0 (
    echo.
    echo [THÀNH CÔNG] Đã cài đặt xong toàn bộ môi trường!
    echo Bây giờ bạn có thể nhấp đúp vào file 'start_client.bat' để chạy.
) else (
    echo.
    echo [CẢNH BÁO] Có lỗi trong quá trình cài đặt thư viện. Vui lòng kiểm tra kết nối mạng.
)

pause

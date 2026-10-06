# BÁO CÁO PHÂN TÍCH TOÀN BỘ PHIÊN CHAT: LÀM RÕ Ý MUỐN & ĐẶC TẢ HỆ THỐNG

> **Mục đích:** Rà soát lại 100% toàn bộ lịch sử trao đổi từ đầu phiên chat đến nay, xâu chuỗi toàn bộ ý muốn thực sự của bạn, đối chiếu với những gì đã triển khai, và chỉ ra rõ ràng các điểm còn mơ hồ để bạn xác nhận.

---

## 1. DÒNG THỜI GIAN VÀ NGUYÊN VĂN CÁC YÊU CẦU CỦA BẠN (Chronological Audit)

Qua 26 lượt trao đổi, hành trình phát triển hệ thống được tóm lược qua 6 giai đoạn rõ rệt:

```mermaid
timeline
    title Lịch sử phát triển và tiến hóa yêu cầu của bạn
    Giai đoạn 1 (08:12) : Muốn tạo tool ghi lại chi tiết hoạt động Windows gửi về Railway
    Giai đoạn 2 (09:03) : Bỏ lọc quyền riêng tư (Bỏ số 4), ghi lại nguyên bản
    Giai đoạn 3 (09:17) : Đẩy mã nguồn lên GitHub (HoangAnhVNVVD/spy) để cài trên máy khác
    Giai đoạn 4 (19:00) : Quy trình 1 dòng lệnh (tải về -> chạy -> đẩy ngay vào ổ đĩa riêng theo tên máy trên Railway)
    Giai đoạn 5 (22:34) : Quét tất cả ứng dụng đang mở trên Taskbar (Chrome, Antigravity, PowerShell) mỗi 3 giây
    Giai đoạn 6 (22:50) : Cô lập dữ liệu từng máy & Cho phép chọn máy trên Web Dashboard
```

### Chi tiết các phát biểu nguyên văn của bạn:
1. **Lúc 08:12:** *"Ghi lại hoạt động của tôi trên window từng chi tiết sau đó gửi dữ liệu của tôi về máy chủ railway của tôi, tôi muốn tạo tool đó"*
   👉 **Ý muốn:** Cần 1 công cụ chạy trên Windows theo dõi từng chi tiết rồi đẩy về Railway.
2. **Lúc 09:02:** *"Là ví dụ máy tôi đang thao tác gì thì nó sẽ gửi đến server railway lưu vào máy chủ railway ấy đúng không?"*
   👉 **Ý muốn:** Xác nhận tính chất real-time: máy thao tác gì thì trên Railway có ngay cái đó.
3. **Lúc 09:03:** *"Bỏ số 4 đi"*
   👉 **Ý muốn:** Không che giấu/mask dữ liệu quyền riêng tư, muốn ghi lại 100% dữ liệu gốc trung thực.
4. **Lúc 09:17 & 09:26:** *"Up lên chỗ nào đó để tôi có thể cài nó từ máy khác được không mã nguồn ấy? tôi đang sử dụng 1 máy khác và phiên chat này đang được chạy trên máy tính riêng của tôi và máy khác của tôi không thể lấy được mã nguồn của tool đó"*
   👉 **Ý muốn then chốt:** Tool phải được phân phối công khai hoặc qua link để máy tính khác (máy thứ 2, thứ 3...) có thể tải về và chạy ngay mà không cần copy code thủ công từ chat.
5. **Lúc 09:36 & 09:41:** Cung cấp link repo `https://github.com/HoangAnhVNVVD/spy` và GitHub PAT token để đẩy code lên.
6. **Lúc 19:00:**
   > *"/goal tôi muốn khi tôi tải về máy và bấm chạy thì ngay lập tức đẩy theo dõi lên ngay railway"*
   > *Quy trình: tải về . chạy . đẩy ngay hoạt động của máy lên railway lưu trong ổ đĩa . railway sẽ tạo 1 vùng nhớ riêng cho từng máy . lưu ở trên đó với tên máy*
   👉 **Ý muốn cực kỳ cốt lõi:**
   - Quy trình tối giản nhất có thể: Chỉ cần tải về -> bấm chạy -> lập tức có dữ liệu trên Railway.
   - Railway phải **lưu vào ổ đĩa** (disk storage).
   - Railway phải **tạo một vùng nhớ/thư mục riêng biệt cho từng máy**, đặt tên theo tên máy tính.
7. **Lúc 22:34:**
   > *"tôi muốn nó show ra tất cả các task đang sử dụng cập nhật mỗi 3 giây chứ không phải top ví dụ trên thanh taskbar là tôi đang ở 3 phần mềm là chrome, antigravity và powershell cứ mỗi 3 giây gửi về 1 lần"*
   👉 **Ý muốn then chốt về dữ liệu hiển thị:**
   - Không muốn chỉ thấy thống kê top ứng dụng (vốn mang tính tổng hợp sau một khoảng thời gian).
   - Phải nhìn thấy **tất cả ứng dụng đang hiện diện trên thanh Taskbar** của Windows (ví dụ lúc đó bạn mở 3 app: Chrome, Antigravity, PowerShell).
   - Tần suất cập nhật cực nhanh: **cứ mỗi 3 giây gửi về một lần**.
8. **Lúc 22:50:**
   > *"bây giờ nếu tôi có nhiều máy mà tôi muốn xem riêng mỗi máy thì phải cô lập ra chứ cho phép chọn máy để xem /plan /goal"*
   👉 **Ý muốn then chốt về quản lý nhiều máy:**
   - Khi chạy trên nhiều máy, dữ liệu không được trộn lẫn.
   - Trên web dashboard phải có **bộ chọn máy tính (selector)** để muốn xem máy nào thì cô lập toàn bộ màn hình chỉ hiển thị riêng dữ liệu máy đó.
9. **Lúc 23:01:** *"redo"*
   👉 Yêu cầu làm lại / rà soát lại.
10. **Lúc 23:16 (Hiện tại):**
    > *"đọc lại tất cả từ đầu phiên chat đến bây giờ hãy làm rõ ý muốn của tôi và liệt kê đầy đủ ý ra 1 file càng rõ càng tốt chỗ nào mơ hồ thì làm rõ lại cho tôi /plan /goal"*

---

## 2. BẢNG LIỆT KÊ TOÀN BỘ Ý MUỐN CỦA BẠN (Detailed Intent Specification)

Dưới đây là 5 trụ cột cấu thành toàn bộ hệ thống mà bạn mong muốn:

| STT | Trụ cột hệ thống | Ý muốn chi tiết của bạn | Tiêu chí đạt chuẩn |
| :--- | :--- | :--- | :--- |
| **1** | **Cài đặt & Triển khai** | Tải về là chạy được ngay trên bất kỳ máy Windows nào, không phụ thuộc môi trường cài đặt phức tạp. | 1 dòng lệnh PowerShell: `irm .../tracker.py -OutFile tracker.py; python tracker.py`. Không cần `pip install`. |
| **2** | **Quét thanh Taskbar** | Nhận diện đúng tất cả ứng dụng đang mở trên thanh Taskbar của Windows. | Phải phân biệt được app đang dùng trực tiếp (`[FOCUS]`) và app đang mở ngầm trên taskbar (`[OPEN]`). Lọc bỏ các tiến trình hệ thống tàng hình. |
| **3** | **Tần suất đồng bộ** | Gửi dữ liệu liên tục về Railway mỗi **3 giây**. | Đồng bộ đúng chu kỳ 3.0s, gửi danh sách taskbar kèm bản ghi hoạt động. |
| **4** | **Phân vùng ổ đĩa Railway** | Mỗi máy tính phải có một vùng nhớ riêng biệt trên ổ đĩa server, lưu theo tên máy. | Thư mục: `data/machines/{tên_máy}/`. Chứa file cấu hình máy, file log stream jsonl, file nhật ký ngày `.log`, và file `current_tasks.json`. |
| **5** | **Giao diện & Cô lập** | Cho phép chọn máy trên Web Dashboard để xem riêng biệt từng máy hoặc xem tất cả. | Dropdown chọn máy trên Navbar. Khi chọn máy nào: Live taskbar, KPI, biểu đồ, top app chỉ hiển thị của máy đó. Hỗ trợ xem file log đĩa. |

---

## 3. NHỮNG ĐIỂM CÒN MƠ HỒ CẦN LÀM RÕ LẠI VỚI BẠN (Ambiguity Audit)

Dưới đây là 5 câu hỏi then chốt xuất phát từ các yêu cầu trước đây, cần sự xác nhận rõ ràng của bạn để hệ thống đi đúng 100% hướng bạn muốn:

### ⚠️ Điểm mơ hồ số 1: Mức độ chi tiết của "Ghi lại hoạt động từng chi tiết"
- **Hiện trạng:** Hệ thống đang ghi lại:
  - Tên tiến trình (Process Name, ví dụ `chrome.exe`, `powershell.exe`).
  - Tiêu đề cửa sổ (Window Title, ví dụ `GitHub - HoangAnhVNVVD/spy - Google Chrome`).
  - Thời gian bắt đầu, kết thúc, thời lượng (Duration seconds).
  - Trạng thái hoạt động (Active) hay rời khỏi máy (Idle/AFK).
  - Danh sách toàn bộ ứng dụng đang mở trên Taskbar mỗi 3 giây.
- **Điểm cần làm rõ với bạn:**
  > *Bạn có muốn dừng ở mức này, hay bạn muốn bổ sung thêm:*
  > 1. Chụp ảnh màn hình định kỳ (Screenshots)?
  > 2. Ghi lại URL chi tiết của từng tab trình duyệt web?
  > 3. Ghi lại các phím đã gõ (Keylogger) hoặc văn bản đã copy (Clipboard)?
  > 4. Giám sát mức độ tiêu thụ CPU / RAM / Mạng của máy?

---

### ⚠️ Điểm mơ hồ số 2: Hình thức chạy của Tool trên máy tính theo dõi
- **Hiện trạng:** Tool hiện tại chạy trong cửa sổ dòng lệnh PowerShell (`python tracker.py`), in ra log trực tiếp:
  `[22:47:12] [*] Đã gửi lên Railway: 3 ứng dụng [FOCUS: Antigravity.exe] | Đang mở: chrome.exe, powershell.exe`.
- **Điểm cần làm rõ với bạn:**
  > *Bạn muốn tool hoạt động theo kiểu nào:*
  > - **Cách A (Hiện tại - Minh bạch):** Hiện cửa sổ terminal để người ngồi máy biết nó đang chạy và thấy log gửi đi.
  > - **Cách B (Chạy ngầm / Ẩn danh hoàn toàn):** Không hiện bất kỳ cửa sổ nào, tự động chạy ngầm dưới nền Windows (Silent Background Process) khi mở máy hoặc khởi động Windows?

---

### ⚠️ Điểm mơ hồ số 3: Tính bền vững của ổ đĩa Railway (Persistent Volume)
- **Hiện trạng:** Dữ liệu từng máy đang lưu vào thư mục ổ đĩa `./data/machines/{tên_máy}/` trên container Railway.
- **Rủi ro kỹ thuật:** Trên Railway, nếu dịch vụ không được gắn **Railway Persistent Volume** thì mỗi khi redeploy (cập nhật code mới) hoặc container khởi động lại, thư mục cục bộ của container sẽ bị làm mới (mất các file log cũ).
- **Điểm cần làm rõ với bạn:**
  > *Bạn có muốn gắn cố định một Railway Volume (ổ cứng lưu trữ vĩnh viễn trên Railway) vào đường dẫn `/app/data` để dữ liệu nhật ký của các máy được lưu giữ mãi mãi kể cả khi nâng cấp hay restart server không?*

---

### ⚠️ Điểm mơ hồ số 4: Quyền truy cập & Bảo mật của Dashboard
- **Hiện trạng:** Truy cập dashboard thông qua token bí mật trên đường dẫn:
  `https://spy-production-8aaa.up.railway.app/?token=hoanganh`.
- **Điểm cần làm rõ với bạn:**
  > *Cách dùng token qua URL như hiện tại đã đủ tiện lợi và an toàn cho bạn chưa, hay bạn muốn có hẳn trang đăng nhập tài khoản / mật khẩu (Login Page) khi mở Dashboard?*

---

### ⚠️ Điểm mơ hồ số 5: Ý nghĩa của chữ "redo" mà bạn nhắn ở lượt trước
- **Hiện trạng:** Ở lượt trước bạn chỉ nhắn duy nhất một từ `"redo"`.
- **Điểm cần làm rõ với bạn:**
  > *Khi bạn nói "redo", ý của bạn là:*
  > - **A:** Viết lại toàn bộ tài liệu giải trình ý muốn và làm rõ hệ thống (chính là file này).
  > - **B:** Xóa sạch toàn bộ dữ liệu mẫu cũ trên Railway để bạn chạy lại máy từ con số 0.
  > - **C:** Bạn chạy code trên máy gặp trục trặc và muốn làm lại cách chạy client?

---

## 4. MA TRẬN ĐỐI CHIẾU: Ý MUỐN VS HIỆN TRẠNG ĐÃ LÀM XONG

| Hạng mục tính năng | Yêu cầu của bạn | Hiện trạng mã nguồn & Railway | Trạng thái |
| :--- | :--- | :--- | :---: |
| **Cài đặt 1 dòng lệnh** | Tải về chạy ngay trên máy khác | File `tracker.py` được host trực tiếp tại `https://spy-production-8aaa.up.railway.app/tracker.py`. Chạy bằng 1 dòng lệnh PowerShell. | ✅ ĐÃ XONG |
| **Quét Taskbar Win32** | Hiện đủ các app taskbar (Chrome, Antigravity, PowerShell...) | Dùng `EnumWindows` + lọc `DWMWA_CLOAKED`, `WS_EX_APPWINDOW`. Nhận diện chính xác 3 app trên máy bạn. | ✅ ĐÃ XONG |
| **Gửi mỗi 3 giây** | Cập nhật real-time chu kỳ 3s | Client cấu hình `sync_interval = 3.0s`. Gửi danh sách taskbar lên `/api/v1/activities/batch`. | ✅ ĐÃ XONG |
| **Phân vùng ổ đĩa riêng** | Tạo thư mục riêng theo tên từng máy trên Railway | Module `MachineStorageManager` tự động tạo `data/machines/{client_id}/` chứa `current_tasks.json`, `machine_info.json`, `daily/*.log`. | ✅ ĐÃ XONG |
| **Bộ chọn máy tính** | Cho phép chọn máy trên Web Dashboard | Thêm dropdown `💻 Chọn máy:` trên Navbar. Hỗ trợ chọn riêng từng máy hoặc chọn `🌐 Tất cả máy tính`. | ✅ ĐÃ XONG |
| **Cô lập dữ liệu máy** | Dữ liệu chỉ hiện theo máy được chọn | Khi chọn máy, toàn bộ Live taskbar, KPI, Timeline, Top Apps, Logs chỉ lọc theo máy đó. | ✅ ĐÃ XONG |
| **Xem log ổ đĩa trực tiếp** | Đọc được file log trên đĩa Railway | Thêm nút `📄 Log đĩa` mở popup xem trực tiếp nội dung file `.log` từ ổ đĩa server. | ✅ ĐÃ XONG |
| **Đồng bộ GitHub & Railway** | Triển khai tự động | Repo `HoangAnhVNVVD/spy` đồng bộ nhánh `main`. Railway service `spy` đang **● Online**. | ✅ ĐÃ XONG |

---

## 5. BƯỚC HÀNH ĐỘNG TIẾP THEO DỰA TRÊN PHẢN HỒI CỦA BẠN

Sau khi đọc qua tài liệu này, bạn chỉ cần xác nhận 5 câu hỏi ở **Mục 3**:
1. *Mức độ chi tiết của hoạt động* (Giữ nguyên như hiện tại hay cần thêm chụp màn hình/keylog/URL)?
2. *Hình thức chạy* (Giữ cửa sổ console hay cần chạy ẩn danh hoàn toàn)?
3. *Ổ đĩa Railway* (Có cần cấu hình Railway Persistent Volume vĩnh viễn không)?
4. *Bảo mật Dashboard* (Dùng token như hiện tại hay làm trang đăng nhập)?
5. *Trải nghiệm thực tế* (Bạn chạy thử dòng lệnh trên máy và xem Dashboard đã ưng ý chưa)?

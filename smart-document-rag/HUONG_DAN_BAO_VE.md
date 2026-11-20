# Hướng dẫn bảo vệ đồ án SmartDoc

**Tên đề tài**  
Nghiên cứu và xây dựng hệ thống tìm kiếm tài liệu thông minh trên nền tảng Web ứng dụng RAG.

**Phạm vi bản trình diễn**  
SmartDoc là ứng dụng quản lý, tìm kiếm và hỏi đáp trích xuất tài liệu. Hệ thống triển khai phần truy xuất thường dùng trong kiến trúc RAG. Kết quả hỏi đáp là đoạn văn lấy từ nguồn, có liên kết để kiểm tra. Bản hiện tại chưa triển khai bước sinh câu trả lời hay tóm tắt tự động.

## 1. Lời mở đầu tham khảo

> Khi có nhiều tài liệu PDF, DOCX và TXT, người dùng thường phải mở từng tệp để tìm một thông tin. Em xây dựng SmartDoc để gom tài liệu vào một kho có phân quyền, tìm theo từ khóa hoặc nhập câu hỏi để xem các đoạn liên quan. Bản hiện tại dùng TF-IDF và cosine similarity để xếp hạng đoạn văn. Người dùng kiểm tra được kết quả bằng cách mở tài liệu nguồn.

## 2. Hệ thống gồm những gì?

| Thành phần | Vai trò | Tệp nên mở khi được hỏi |
|---|---|---|
| Giao diện | HTML, CSS, JavaScript, Jinja2 và Bootstrap hiển thị các trang và form | `templates/`, `static/` |
| Flask | Định tuyến, xác thực phiên, kiểm tra CSRF và phối hợp các bước xử lý | `app.py` |
| Trích xuất tệp | Đọc PDF bằng pypdf, DOCX bằng python-docx, TXT bằng bộ giải mã UTF-8 | `document_files.py` |
| Truy xuất | Chia văn bản, chuẩn hóa tiếng Việt, tính TF-IDF và xếp hạng đoạn | `rag.py` |
| Dữ liệu | PyMySQL thực thi truy vấn tham số hóa tới MariaDB trong XAMPP | `models.py`, `database/schema.sql` |
| Cấu hình | Đọc biến môi trường và cấu hình dung lượng tải lên | `config.py`, `.env.example` |
| Kiểm thử | 10 tài liệu giả lập, 15 câu hỏi có kết quả mong đợi và kiểm thử chia đoạn | `tests/retrieval_cases.json`, `tests/test_retrieval.py` |

Luồng kiến trúc có thể vẽ trên bảng bằng bốn khối: **Trình duyệt → Flask → MariaDB và thư mục tệp gốc → Kết quả hiển thị bằng Jinja2**. scikit-learn chạy trong tiến trình Flask khi cần xếp hạng.

### Dữ liệu lưu ở đâu?

- `users` lưu tài khoản, mật khẩu băm, vai trò và bộ đếm tìm kiếm, hỏi đáp. `admins` hỗ trợ tương thích với cấu hình cũ.
- `documents` lưu tên, loại tệp, dung lượng, nội dung trích xuất và chủ sở hữu. `document_chunks` lưu các đoạn với thứ tự trong tài liệu và số trang nếu có.
- Một người dùng có thể sở hữu nhiều tài liệu. Một tài liệu có nhiều đoạn. Khóa của đoạn là cặp `(document_id, chunk_index)`. Cơ sở dữ liệu dùng `utf8mb4` để lưu tiếng Việt.
- Tệp gốc của bản tải lên mới nằm trong `instance/originals/`, đặt tên theo ID tài liệu và được tải xuống qua Flask sau khi kiểm tra quyền. Với bản ghi cũ thiếu tệp gốc, hệ thống trả TXT từ văn bản đã trích xuất. Sao lưu MySQL và thư mục tệp gốc cùng nhau nếu cần khôi phục đầy đủ.

## 3. Ba luồng cần giải thích khi trình bày

### Tải lên

Flask kiểm tra phiên đăng nhập và CSRF, rồi kiểm tra phần mở rộng, cấu trúc và dung lượng tệp. Giới hạn hiện tại là **10 MB mỗi tệp, tối đa 10 tệp mỗi lượt**. PDF được đọc theo trang, DOCX đọc đoạn văn và ô bảng, TXT được kiểm tra mã hóa UTF-8. Hệ thống chia nội dung thành đoạn tối đa khoảng **900 ký tự** với phần chồng lấn tối đa **120 ký tự**. Mỗi tệp hợp lệ được lưu độc lập. Khi lưu một tệp, bản ghi tài liệu và các đoạn dùng chung giao dịch MariaDB. Mã có xử lý rollback và dọn tệp đã ghi nếu gặp lỗi trong quá trình lưu.

### Tìm kiếm từ khóa

Ở `/search`, MariaDB tìm chuỗi người dùng nhập trong văn bản trích xuất bằng `LOCATE`. Ứng dụng lấy một đoạn ngắn quanh vị trí khớp và hiển thị liên kết tới tài liệu. Truy vấn giới hạn phạm vi theo quyền tài khoản.

### Hỏi đáp trích xuất

1. Nhận câu hỏi và truy vấn các đoạn mà tài khoản được phép đọc. Với tài liệu cũ chưa có đoạn lưu sẵn, hệ thống chia trong bộ nhớ.
2. Chuẩn hóa chữ hoa thường và dấu tiếng Việt, xử lý `đ` thành `d` trong chuỗi so sánh, rồi bỏ một số từ thông dụng. Văn bản gốc dùng để hiển thị vẫn giữ dấu.
3. Dùng TF-IDF để chuyển câu hỏi và các đoạn thành vector. Từ phổ biến trong toàn bộ kho được giảm trọng số. Phiên bản hiện tại dùng đặc trưng một âm tiết và cặp âm tiết liền kề, ví dụ “thư viện”.
4. Tính cosine similarity giữa vector câu hỏi và từng đoạn. Chọn tối đa **3 đoạn** có điểm từ **0,18** trở lên.
5. Hiển thị nguyên văn đoạn trích, tên tài liệu, số đoạn và số trang nếu được lưu. Nếu mọi đoạn đều dưới ngưỡng, trang báo không tìm thấy nội dung phù hợp.

**Ví dụ để giải thích thuật toán:** Câu hỏi “thoi han muon tai lieu” được so sánh dưới dạng đã chuẩn hóa với đoạn “Thời hạn mượn tài liệu là 14 ngày.” Cặp “thời hạn” và “tài liệu” góp phần tăng điểm. Giao diện vẫn hiển thị câu gốc có dấu. Điểm cosine là điểm tương đồng văn bản, không phải xác suất câu trả lời đúng.

## 4. Kịch bản demo 6–8 phút

### Chuẩn bị trước buổi bảo vệ

- Bật **MySQL** trong XAMPP. Chuẩn bị tài khoản User, một tài khoản User khác để kiểm tra phân quyền và tài khoản Admin. Dùng dữ liệu minh họa riêng cho buổi demo.
- Chạy Flask từ PowerShell. Nếu cổng đang chạy phiên cũ, dừng đúng phiên của dự án trước khi khởi động lại.

```powershell
cd C:\DATN\smart-document-rag
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m flask --app app run --port 5001
```

- Mở `http://127.0.0.1:5001/login`. Khi cài mới, chuẩn bị cơ sở dữ liệu theo `database/schema.sql` và cấu hình `.env`. Với cơ sở dữ liệu đang dùng, kiểm tra cấu trúc hiện có trước khi import SQL.
- Tệp mẫu có sẵn là `uploads/huong-dan-do-an.txt`. Bạn có thể chuẩn bị thêm DOCX có một bảng và PDF có lớp văn bản. Kiểm tra trước số trang có hiển thị hay chỉ có số đoạn, tùy dữ liệu đã lưu và cột `page_number` của cơ sở dữ liệu.

| Thời lượng | Thao tác | Điểm cần nói |
|---|---|---|
| 1 phút | Đăng nhập User và mở Dashboard | Mỗi tài khoản có kho và thống kê riêng |
| 1–2 phút | Tải TXT hoặc DOCX, mở chi tiết và tải xuống | Phân biệt tệp gốc với văn bản trích xuất |
| 1 phút | Tìm từ khóa “đồ án” với tệp mẫu đã tải | Truy vấn chuỗi và đoạn xem trước |
| 1–2 phút | Hỏi “Sinh viên cần nộp những gì khi làm đồ án?” rồi mở nguồn | Kết quả là đoạn trích xếp hạng, người dùng có thể đối chiếu |
| 1 phút | Hỏi “Quỹ đạo Sao Hải Vương?” trên kho demo | Hệ thống có trạng thái thiếu nội dung phù hợp |
| 1 phút | Dùng tài khoản khác thử URL chi tiết của tài liệu vừa tải, rồi mở `/admin` | Tài liệu ngoài quyền trả 404. User vào trang Admin nhận 403 |

Khi có thời gian, mở `document_chunks` trong phpMyAdmin để minh họa mối liên hệ với tài liệu. Không mở nội dung `.env`, mật khẩu hoặc cookie trước hội đồng.

## 5. Câu hỏi thường gặp khi bảo vệ

**Đây có phải RAG hoàn chỉnh không?**  
Bản hiện tại hoàn thành khâu truy xuất và hiển thị đoạn nguồn. RAG sinh câu trả lời đầy đủ còn có bước đưa ngữ cảnh được truy xuất vào mô hình sinh. Đề tài có thể giới thiệu kiến trúc RAG như hướng nghiên cứu và trình bày rõ phạm vi ứng dụng đã triển khai.

**Vì sao chọn TF-IDF thay vì embedding?**  
TF-IDF chạy cục bộ, dễ giải thích và phù hợp quy mô đồ án. Nó mạnh khi câu hỏi và đoạn nguồn có từ vựng chung. Câu diễn đạt bằng từ đồng nghĩa hoặc khác ngôn ngữ có thể cho điểm thấp. Embedding và chỉ mục chuyên dụng là hướng so sánh ở quy mô lớn hơn.

**Vì sao cần chia đoạn và có phần chồng lấn?**  
Một tài liệu dài có thể chứa nhiều chủ đề. Chia đoạn giúp xếp hạng theo phần nhỏ hơn. Chồng lấn giảm khả năng mất thông tin tại ranh giới hai đoạn, đổi lại có thể xuất hiện hai đoạn gần giống nhau.

**Tại sao dùng ngưỡng 0,18 và chỉ lấy ba đoạn?**  
Đây là tham số của bản hiện tại để giới hạn kết quả yếu và giữ giao diện dễ đọc. Có thể đánh giá thêm bằng bộ câu hỏi đa dạng, đo độ chính xác top-k và tỷ lệ bỏ sót rồi điều chỉnh ngưỡng.

**Người dùng sửa ID trên URL thì sao?**  
Flask và các truy vấn trong `models.py` kiểm tra vai trò hoặc chủ sở hữu cho xem, tải xuống, xóa, tìm kiếm và hỏi đáp. Điều kiện truy cập được áp dụng trước khi tài liệu được đưa vào thuật toán truy xuất.

**Ứng dụng bảo vệ mật khẩu và dữ liệu như thế nào?**  
Werkzeug băm mật khẩu. Flask dùng session ký bằng `SECRET_KEY`. Các form POST có CSRF. Truy vấn nhận dữ liệu qua tham số. Tệp gốc nằm ngoài thư mục static và được phục vụ qua route có phân quyền.

**PDF scan và tài liệu cũ xử lý thế nào?**  
PDF chỉ chứa ảnh cần OCR, hiện ngoài phạm vi. Số trang hiển thị khi có metadata đã lưu. Với dữ liệu cũ thiếu metadata, hệ thống hiển thị số đoạn. DOCX và TXT dùng số đoạn vì quá trình trích xuất không xác định trang trình bày ổn định.

**Đã kiểm chứng chất lượng thế nào?**  
Bộ thử gồm 10 văn bản và 15 câu hỏi. Kết quả chạy trên bộ mẫu đạt đúng kỳ vọng ở 15/15 câu, gồm trường hợp có nguồn và không có nguồn. Đây là kết quả trên bộ thử nhỏ. Ở quy mô lớn, việc tính lại TF-IDF mỗi lượt hỏi có thể tăng độ trễ. Có thể đánh giá tiếp với dữ liệu thực tế và chỉ mục được cập nhật khi tài liệu thay đổi.

## 6. Xử lý sự cố trước buổi demo

| Triệu chứng | Cách kiểm tra |
|---|---|
| Giao diện hoặc route vẫn là bản cũ | Xác nhận tiến trình Flask đúng thư mục và đúng cổng. Khởi động lại phiên của dự án rồi nhấn Ctrl+F5 |
| Flask không kết nối MariaDB | Kiểm tra MySQL trong XAMPP và host, cổng, tên cơ sở dữ liệu trong `.env` |
| PDF báo thiếu nội dung | Mở PDF và thử chọn văn bản. Với tệp scan, dùng PDF có lớp văn bản để demo |
| Hỏi đáp không tìm thấy | Kiểm tra đã đăng nhập đúng tài khoản có quyền đọc tài liệu và thử một cụm từ xuất hiện trong nguồn |
| Không thấy số trang | Kiểm tra loại tệp, cột `page_number` và dữ liệu của đoạn. Kết quả vẫn có số đoạn để đối chiếu |

Chạy lại bộ kiểm thử trước buổi bảo vệ:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```


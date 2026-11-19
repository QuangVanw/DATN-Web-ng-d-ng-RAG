# Hệ thống tìm kiếm tài liệu thông minh

Đồ án Flask và MySQL. Giai đoạn 1 cung cấp đăng nhập quản trị, tải lên, liệt kê, xem văn bản và xóa tài liệu PDF/TXT. MySQL lưu tên, dung lượng, loại tệp và văn bản trích xuất. Thư mục `uploads/` chứa dữ liệu mẫu để tải lên từ trình duyệt. Giai đoạn 2 thêm tìm kiếm từ khóa. Trang hỏi đáp hiện dùng truy xuất đoạn trích bằng TF-IDF.

## Import cơ sở dữ liệu bằng phpMyAdmin

1. Mở **XAMPP Control Panel**, nhấn **Start** ở dòng **Apache** và **MySQL**. Mô-đun MySQL của XAMPP chạy MariaDB.
2. Nhấn **Admin** ở dòng **MySQL** hoặc mở http://localhost/phpmyadmin/. Nếu phpMyAdmin yêu cầu đăng nhập, dùng tài khoản MariaDB có quyền tạo cơ sở dữ liệu và bảng.
3. Ở trang chính phpMyAdmin, mở thẻ **Import / Nhập**, chọn tệp `database/schema.sql`, đặt bộ ký tự của tệp là **utf-8** và định dạng là **SQL**, rồi nhấn **Import** hoặc **Go**.
4. Chọn `smart_document_rag` ở thanh bên và mở **Structure / Cấu trúc**. Bảng `admins` có các cột `id`, `username`, `password_hash`. Bảng `documents` có các cột `id`, `filename`, `file_type`, `size_bytes`, `content`, `created_at`. Cột `content` lưu toàn bộ văn bản trích xuất dưới dạng `MEDIUMTEXT`.

Bảng `document_chunks` lưu các đoạn văn dùng cho hỏi đáp. Schema dùng InnoDB và khai báo `utf8mb4` trực tiếp cho các bảng mới. Khi import lại, `IF NOT EXISTS` giữ các bảng và bản ghi hiện có. Với bảng có từ trước, phpMyAdmin có thể báo bảng đã tồn tại. Nếu bảng cũ dùng cấu trúc hoặc bộ ký tự khác, cần đối chiếu và lập kế hoạch chuyển đổi riêng.

## Chạy Flask trên Windows

Cần Python 3.10 trở lên. Mở PowerShell và chạy:

```powershell
cd C:\DATN\smart-document-rag
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
notepad .env
```

- Với tệp `.env` mới, dán chuỗi vừa sinh vào `SECRET_KEY`.
- Đặt `MYSQL_HOST=127.0.0.1`, `MYSQL_PORT=3306` và `MYSQL_DATABASE=smart_document_rag`. Nếu XAMPP dùng cổng khác, điền cổng hiển thị ở dòng **MySQL** trong Control Panel.
- Điền tài khoản MariaDB vào `MYSQL_USER` và `MYSQL_PASSWORD`. Nếu tài khoản `root` trên XAMPP cục bộ có mật khẩu trống, dùng `MYSQL_USER=root` và giữ `MYSQL_PASSWORD=`. Đặt mật khẩu có khoảng trắng hoặc ký tự `#` trong dấu nháy.

Nếu chưa có tài khoản quản trị web, chạy lệnh tạo tài khoản và nhập mật khẩu khi được hỏi:

```powershell
.\.venv\Scripts\python.exe -m flask --app app create-admin admin
```

Khởi động Flask và mở http://127.0.0.1:5000:

```powershell
.\.venv\Scripts\python.exe -m flask --app app run
```

Đăng nhập bằng tài khoản quản trị web vừa tạo hoặc tài khoản đã có trong bảng `admins`.

## Kết nối và giới hạn gói dữ liệu

- **Connection refused**. Kiểm tra mô-đun MySQL đã chạy và `MYSQL_PORT` trùng với cổng XAMPP.
- **Access denied**. Kiểm tra tài khoản và mật khẩu MariaDB trong `.env`.
- **Unknown database** hoặc **Table doesn't exist**. Kiểm tra kết quả import và tên cơ sở dữ liệu trong `.env`.
- **Packet too large** hoặc mất kết nối khi lưu văn bản dài. Trong thẻ **SQL** của phpMyAdmin, chạy `SHOW VARIABLES LIKE 'max_allowed_packet';`. Nếu giá trị là 1 MB, mở **Config → my.ini** ở dòng MySQL trên XAMPP Control Panel, chỉnh hoặc thêm `max_allowed_packet=16M` trong mục `[mysqld]`, khởi động lại mô-đun MySQL và kiểm tra lại giá trị. Xem [biến max_allowed_packet của MariaDB](https://mariadb.com/docs/server/server-management/variables-and-modes/server-system-variables#max_allowed_packet).


## Kiểm tra chức năng

1. Khi chưa đăng nhập, truy cập `/documents` và kiểm tra trình duyệt chuyển về trang đăng nhập. Thử sai mật khẩu để kiểm tra thông báo, sau đó đăng nhập đúng.
2. Tải `uploads/tai-lieu-mau.txt` và `uploads/huong-dan-do-an.txt`. Kiểm tra tên và văn bản tiếng Việt ở trang chi tiết và danh sách.
3. Để thử PDF, mở một tài liệu có văn bản trong Word hoặc trình duyệt rồi in bằng Microsoft Print to PDF. Tải PDF lên và kiểm tra nội dung. PDF scan chỉ có ảnh cần OCR, hiện chưa được hỗ trợ.
4. Thử tệp có đuôi khác PDF/TXT, TXT rỗng hoặc tệp vượt giới hạn 10 MB. Kiểm tra ứng dụng từ chối và danh sách không có bản ghi mới.
5. Mở một tài liệu, chọn Xóa và xác nhận. Tải lại danh sách để kiểm tra bản ghi đã được xóa. Đăng xuất và truy cập lại `/documents`.

Nếu Flask báo lỗi khi kết nối, kiểm tra dịch vụ MySQL, thông tin trong `.env` và việc chạy schema. TXT được đọc dưới dạng UTF-8, còn PDF có mật khẩu hoặc trên 200 trang sẽ bị từ chối.

## Hỏi đáp tài liệu bằng truy xuất đoạn trích

Trang **Hỏi đáp tài liệu** (`/chat`) dùng scikit-learn để so sánh câu hỏi với các đoạn văn theo TF-IDF và cosine similarity. Tiếng Việt được chuẩn hóa hoa thường, có dấu và không dấu. Mô hình dùng cả âm tiết đơn và cặp âm tiết liền kề để giữ thêm tín hiệu từ các cụm như “thư viện”. Hệ thống trả tối đa ba đoạn trên ngưỡng 0,18, kèm nguồn, hoặc báo không tìm thấy nội dung phù hợp. Đây là hỏi đáp trích xuất. Hệ thống hiển thị văn bản từ tài liệu và không có bước sinh câu trả lời của RAG.

PDF, DOCX và TXT mới được chia đoạn và lưu cùng giao dịch tải lên. Tài liệu cũ có sẵn đoạn sẽ dùng lại dữ liệu đó. Nếu chưa có đoạn, Flask chia nội dung cũ trong bộ nhớ khi tra cứu. Nếu cần hiển thị trang cho PDF tải lên sau này, duyệt rồi import [migration 004](database/migrations/004_chunk_page_number.sql). Nếu chưa áp dụng migration, trang hỏi đáp vẫn hiển thị tên tài liệu và số đoạn.

Bật MySQL trong XAMPP và khởi động lại đúng Flask của dự án:

```powershell
cd C:\DATN\smart-document-rag
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m flask --app app run --port 5001
```

Mở http://127.0.0.1:5001/chat sau khi đăng nhập. Tải `uploads/tai-lieu-mau.txt` lên rồi hỏi “Thời hạn mượn tài liệu là bao nhiêu ngày?”. Thử thêm “Quỹ đạo Sao Hải Vương?” để kiểm tra trạng thái không tìm thấy. Chạy bộ kiểm thử 10 tài liệu và 15 câu hỏi bằng lệnh:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

## SmartDoc AI — chuẩn bị nâng cấp

### Hiện trạng

Bản hiện tại chạy với Flask và MariaDB của XAMPP. Quản trị viên có thể đăng nhập, tải một PDF văn bản hoặc TXT mỗi lần, xem và xóa tài liệu. Ứng dụng lưu văn bản trích xuất, tìm theo nội dung và dùng TF-IDF để chọn đoạn cho RAG. Hỏi đáp cần khóa và tên model của nhà cung cấp API. Bảng đoạn văn đã có khóa ngoại xóa theo tài liệu.

Đợt rà soát xác nhận kết nối MariaDB 10.4.32, cổng 3306, các trang của bản đang có và việc chuyển hướng khách chưa đăng nhập. Môi trường này chưa cấu hình đủ LLM API để kiểm thử câu trả lời thật. Giới hạn gói MariaDB đang là 1 MB, có thể gây lỗi khi lưu văn bản trích xuất dài. Xem mục **Kết nối và giới hạn gói dữ liệu**.

### Migration chờ duyệt

[`database/migrations/001_users_and_document_ownership.sql`](database/migrations/001_users_and_document_ownership.sql) bổ sung bảng `users` và các cột chủ sở hữu, mã lưu tệp gốc, danh mục trong `documents`. Danh sách định dạng được mở rộng để chuẩn bị cho DOCX. Bảng `admins` được giữ lại, tên đăng nhập và hash được sao chép vào `users`. Email có thể để trống cho quản trị viên cũ. Đăng ký mới sẽ yêu cầu email trong Flask.

Tài liệu cũ có `user_id` và `storage_key` rỗng vì dữ liệu hiện tại thiếu thông tin về chủ sở hữu và tệp gốc. Giai đoạn 2 sẽ cho quản trị viên truy cập những tài liệu này và vẫn hiển thị văn bản đã trích xuất. Tải xuống tệp gốc sẽ áp dụng cho tài liệu mới. Tệp mới sẽ được lưu bằng mã ngẫu nhiên trong thư mục riêng ngoài `static` và Flask kiểm tra quyền trước khi phục vụ tệp.

Sau khi migration được duyệt, xuất bản sao SQL của `smart_document_rag` trong phpMyAdmin và dừng Flask. Chạy thử trên bản sao dữ liệu trước khi import qua thẻ **Import** trên môi trường đang dùng. Tệp có lệnh `USE smart_document_rag`. Để thử trên schema khác, sửa dòng đó trên bản sao của tệp SQL. Sau khi chạy, đối chiếu số tài liệu và đoạn văn, kiểm tra cột mới, khóa ngoại và số quản trị viên được sao chép. MariaDB thực hiện commit ngầm với DDL, vì vậy bản sao lưu là điểm khôi phục. Các câu lệnh tạo bảng, thêm cột và sao chép được viết để có thể chạy lại với cùng cấu trúc dự kiến.

### Thứ tự triển khai

1. Giai đoạn 2 chuyển Flask sang `users`, yêu cầu đăng nhập lại, thêm đăng ký và kiểm tra vai trò, chủ sở hữu trong mọi truy vấn tài liệu. Cần áp dụng giới hạn quyền cho cả tìm kiếm và hỏi đáp hiện có ngay khi mở đăng ký. Tiếp theo là upload nhiều tệp PDF/DOCX/TXT, tối đa 10 MB mỗi tệp, và tải xuống qua route có phân quyền.
2. Giai đoạn 3 thêm giao diện SmartDoc AI tiếng Việt với dashboard, sidebar và Bootstrap 5.
3. Giai đoạn 4 mở rộng tìm kiếm theo tên, nội dung, tập tài liệu được chọn và vị trí đoạn khi có.
4. Giai đoạn 5 bổ sung chọn tài liệu cho RAG và chuẩn hóa hiển thị nguồn. Giai đoạn 6 thêm tóm tắt, lịch sử, thống kê và quản trị. Lịch sử và thống kê sẽ có migration riêng khi thiết kế chức năng.
5. Giai đoạn 7 kiểm thử tổng thể trên Windows. Tiêu chí quan trọng là hai tài khoản thường không thể truy cập tài liệu của nhau qua URL chi tiết, tải xuống, xóa, tìm kiếm hoặc RAG.

Nếu từng sao chép `SECRET_KEY` từ bản cũ của `.env.example`, hãy tạo khóa ngẫu nhiên mới theo phần hướng dẫn Windows, cập nhật `.env` và khởi động lại Flask. Trình duyệt sẽ cần đăng nhập lại.

## SmartDoc AI — giao diện và tải lên DOCX

1. Trong PowerShell tại thư mục dự án, cài thư viện mới bằng `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`.
2. Với cơ sở dữ liệu hiện có dùng `ENUM('pdf','txt')`, chờ phê duyệt rồi sao lưu và import riêng [migration DOCX](database/migrations/002_allow_docx_only.sql) qua phpMyAdmin. Migration này chỉ bổ sung định dạng DOCX. PDF/TXT tiếp tục hoạt động trong khi chờ duyệt. Với cơ sở dữ liệu mới, `database/schema.sql` đã có DOCX.
3. Trong terminal đang chạy đúng Flask của dự án trên cổng 5001, nhấn **Ctrl+C**. Chạy `.\.venv\Scripts\python.exe -m flask --app app run --port 5001`. Mở http://127.0.0.1:5001/ và tải lại trang. Bootstrap 5 được nạp qua CDN, còn CSS và JavaScript riêng có phiên bản trong URL để trình duyệt lấy bản mới.
4. Vào **Tài liệu của tôi**, chọn tối đa 10 tệp PDF/DOCX/TXT. Giới hạn mỗi tệp là 10 MB. Kết quả tải lên hiển thị trạng thái theo từng tệp, các tệp hợp lệ được lưu kể cả khi tệp khác trong cùng lượt bị từ chối. PDF scan cần OCR. DOCX hỗ trợ đoạn văn và nội dung bảng.
5. **Tải xuống** trả tệp gốc của các tài liệu tải từ phiên bản mới. Tệp nằm trong `instance/originals/`, ngoài thư mục tệp tĩnh. Các tài liệu đã lưu từ phiên bản cũ chỉ có văn bản trích xuất, nên chức năng trả một tệp TXT chứa nội dung hiện có. Sao lưu thư mục `instance/originals/` cùng cơ sở dữ liệu nếu cần giữ tệp gốc.

Trang **Tóm tắt tài liệu** cho phép chọn tài liệu và hiển thị trạng thái tích hợp. Trang **Quản trị** dùng tài khoản quản trị hiện có. Thống kê lượt tìm kiếm và hỏi đáp hiển thị chưa có dữ liệu cho tới khi có chức năng lưu lượt sử dụng.

## Tài khoản và quyền sở hữu tài liệu

Trước khi mở đăng ký trên cơ sở dữ liệu hiện có, sao lưu bằng phpMyAdmin, dừng Flask và import [migration tài khoản 003](database/migrations/003_accounts_and_document_access.sql) **sau khi được phê duyệt**. Migration này áp dụng độc lập và giữ nguyên cấu hình DOCX. Với cơ sở dữ liệu mới, `database/schema.sql` đã có bảng `users`. Ưu tiên dùng migration 003 cho chức năng tài khoản. Tệp 001 là bản chuẩn bị trước đây.

Migration sao chép tài khoản quản trị và mật khẩu đã băm. Nếu có đúng một quản trị viên cũ, tài liệu chưa có chủ sở hữu được gán cho tài khoản đó. Nếu có nhiều quản trị viên cũ, các tài liệu thiếu chủ sở hữu vẫn có thể do quản trị viên quản lý. Flask yêu cầu đăng nhập lại sau khi chuyển sang bảng `users`.

Bật **MySQL** trong XAMPP và chạy trong PowerShell tại thư mục dự án:

```powershell
.\.venv\Scripts\python.exe -m flask --app app run --port 5001
```

Mở http://127.0.0.1:5001/register và đăng ký hai tài khoản thử riêng. Đăng nhập lần lượt, tải tài liệu thử và kiểm tra rằng chỉ chủ sở hữu thấy tài liệu trong danh sách, tìm kiếm, hỏi đáp và tóm tắt. Thử mở URL chi tiết hoặc tải xuống của tài khoản kia và xác nhận phản hồi 404. Tài khoản thường truy cập `/admin` sẽ nhận 403. Đăng nhập quản trị viên cũ để xác nhận vẫn có quyền quản lý tài liệu đã lưu.

Tổng quan đếm lượt tìm kiếm có từ khóa và lượt hỏi đáp xử lý thành công cho từng tài khoản từ khi migration được áp dụng. Trong lúc chờ migration, tài khoản quản trị cũ tiếp tục hoạt động và trang đăng ký hiển thị trạng thái chờ cập nhật.

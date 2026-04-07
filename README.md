# DriverLinux

Bản phục dựng và mở rộng từ một repo C/Linux bị mất mã nguồn gốc và hỏng một phần artefact.

Repo hiện có thể tách thành 2 bài độc lập:

- bài 1: hệ thống quản lý sinh viên
- bài 2: driver USB bàn phím

Trong đó bài 1 có 3 lớp giao diện:

- ứng dụng C user-space giữ tính tương thích với binary cũ
- ứng dụng desktop PyQt5 để thao tác bằng giao diện
- ứng dụng web Python chạy trên trình duyệt local

## Thành phần chính

### Bài 1: Quản lý sinh viên

- `student_mgmt`: chương trình C user-space
- `student_app.py`: ứng dụng desktop PyQt5
- `student_web.py`: ứng dụng web local
- `auth.c`, `student.c`, `sha256.c`: lõi xử lý đăng nhập và dữ liệu
- `string_utils.c`, `string_utils.h`: wrapper chuẩn hóa chuỗi cho bài 1
- `driver/string_utils_shared.h`: lõi chuẩn hóa xâu dùng chung đặt trong thư mục `driver`

### Bài 2: Driver USB bàn phím

- `kb_driver`: khung kernel module phục dựng từ artefact còn sót lại
- `keyboard_dashboard.py`: dashboard local cho bài driver USB bàn phím
- `keyboard_dashboard_app.py`: dashboard desktop PyQt5 cho bài driver USB bàn phím

## Tính năng hiện tại

### Xác thực

- Dữ liệu đăng nhập được lưu trong `users.dat`
- Mật khẩu được lưu dưới dạng hash
- Tài khoản mặc định:
  - username: `admin`
  - password: `admin123`
- Mỗi sinh viên có tài khoản riêng:
  - username = mã sinh viên
  - mật khẩu mặc định khi tạo mới = `1`

### Quản lý sinh viên

Hệ thống quản lý các trường:

- mã sinh viên
- họ và tên
- lớp
- địa chỉ
- số điện thoại
- ngành học
- GPA

Admin có thể:

- thêm sinh viên
- sửa sinh viên
- xóa sinh viên
- sửa GPA chính thức
- xem toàn bộ thông tin và password hash
- đổi mật khẩu

Sinh viên có thể:

- xem danh sách công khai của sinh viên khác
- xem hồ sơ cá nhân đầy đủ của chính mình
- sửa hồ sơ cá nhân của chính mình
- đổi mật khẩu
- tính GPA dự kiến bằng danh sách môn học tự nhập

Sinh viên không được:

- sửa GPA chính thức của mình
- xem địa chỉ, số điện thoại, GPA của sinh viên khác trong danh sách công khai

### Tính GPA dự kiến

Ứng dụng desktop và web đều hỗ trợ tính `GPA dự kiến` cho sinh viên.

Tính năng này:

- lưu riêng theo từng sinh viên
- dùng danh sách môn học tự nhập
- không ghi đè `GPA` chính thức trong hồ sơ

Mỗi môn học gồm:

- tên môn
- số tín
- điểm

Công thức:

```text
GPA = tổng(điểm * số tín) / tổng số tín
```

## Cấu trúc file quan trọng

- `main.c`: menu và luồng chương trình C
- `auth.c`, `auth.h`: nạp/lưu user và xác thực
- `student.c`, `student.h`: nạp/lưu danh sách sinh viên
- `sha256.c`, `sha256.h`: hàm hash
- `string_utils.c`, `string_utils.h`: API chuẩn hóa chuỗi của bài 1
- `driver/string_utils_shared.h`: lõi chuẩn hóa xâu đặt trong thư mục `driver` và được bài 1 dùng lại
- `student_app.py`: ứng dụng desktop
- `student_web.py`: ứng dụng web
- `common.h`: các hằng số và struct dùng chung
- `driver/usb_keyboard.c`: lõi driver USB bàn phím của bài 2

## Chạy chương trình C

Build:

```sh
make
```

Chạy:

```sh
./student_mgmt
```

## Chạy ứng dụng desktop

Yêu cầu:

- Python 3
- PyQt5

Chạy:

```sh
python3 student_app.py
```

Hoặc:

```sh
make app
```

## Chạy ứng dụng web

Chạy:

```sh
python3 student_web.py
```

Hoặc:

```sh
make webui
```

Mặc định web app chạy tại:

```text
http://127.0.0.1:8000
```

## Định dạng dữ liệu

### `users.dat`

File nhị phân gồm các bản ghi lặp lại:

- 32 byte username
- 64 byte password hash

File này lưu hash của:

- admin
- tất cả tài khoản sinh viên

### `students.dat`

File text.

Dữ liệu cũ vẫn đọc được theo 3 dòng:

1. Mã sinh viên
2. Họ và tên
3. Lớp

Dữ liệu mới được ghi với header `STUDENT_V2` và 7 trường:

1. Mã sinh viên
2. Họ và tên
3. Lớp
4. Địa chỉ
5. Số điện thoại
6. Ngành học
7. GPA

### `gpa_trials.json`

File JSON lưu danh sách môn học tự nhập để tính GPA dự kiến theo từng `student_id`.

File này:

- dùng chung cho desktop app và web app
- không thay thế `GPA` chính thức trong `students.dat`

## Quyền truy cập

### Admin

- xem toàn bộ thông tin sinh viên
- thấy được password hash trong desktop app
- thêm, sửa, xóa sinh viên
- sửa GPA
- đổi mật khẩu

### Sinh viên

- xem danh sách công khai của sinh viên khác:
  - mã sinh viên
  - họ và tên
  - lớp
  - ngành học
- xem đầy đủ thông tin của chính mình
- sửa thông tin cá nhân của chính mình, trừ GPA
- đổi mật khẩu
- tính GPA dự kiến

## Ghi chú cho bài 1

- bài 1 sử dụng hàm chuẩn hóa xâu được xây dựng trong thư mục `driver`
- phần chương trình C của bài 1 gọi `normalize_str()` trong `string_utils.c`
- phần xử lý chuẩn hóa lõi dùng chung nằm ở `driver/string_utils_shared.h`
- hệ thống đăng nhập bằng `username` và `password`, trong đó mật khẩu được băm bằng SHA-256

## Build kernel module

Cần Linux headers cho kernel đang chạy:

```sh
make -f Makefile.kmod
```

## Dashboard cho bài 2: Driver USB bàn phím

Driver USB bàn phím được mở rộng để:

- ghi nhận sự kiện `pressed` và `released`
- giữ lịch sử sự kiện gần nhất trong bộ đệm vòng
- thống kê số lần nhấn/thả theo từng mã phím
- xuất trạng thái qua `/proc/kb_driver`

Các lệnh điều khiển hỗ trợ qua `/proc/kb_driver`:

- `clear_history`
- `reset_stats`
- `logging=1`
- `logging=0`

Chạy dashboard local:

```sh
python3 keyboard_dashboard.py
```

Hoặc:

```sh
make kbdash
```

Chạy dashboard desktop:

```sh
python3 keyboard_dashboard_app.py
```

Hoặc:

```sh
make kbdash-app
```

Mặc định dashboard chạy tại:

```text
http://127.0.0.1:8081
```

Dashboard hiển thị:

- trạng thái module
- danh sách USB keyboard interface
- lịch sử sự kiện gần nhất
- thống kê theo mã phím
- nút bind/unbind và điều khiển logging

Lưu ý:

- thao tác `bind/unbind` và ghi vào `/proc/kb_driver` có thể cần quyền `root`
- nếu muốn điều khiển trực tiếp từ dashboard, nên chạy bằng quyền phù hợp trong môi trường local test

## Ghi chú

- Phần user-space C ban đầu được phục dựng để giữ hành vi gần với binary `demo_p1`
- `students.dat` được mở rộng để phục vụ desktop app và web app
- Repo hiện có cả source, file build và một số file dữ liệu runtime
- Phần driver USB bàn phím hiện có thể được tách thành bài riêng với giao diện dashboard local để trình diễn

## Giới hạn

- Một phần artefact gốc đã hỏng hoặc không còn đủ để phục dựng đầy đủ module kernel ban đầu
- Web app hiện chạy local, không phải một hệ thống production hardening
- Ứng dụng C user-space chưa được mở rộng đầy đủ UI/phân quyền như desktop app và web app

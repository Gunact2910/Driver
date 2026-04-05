# DriverLinux

Bản phục dựng và mở rộng từ một repo C/Linux bị mất mã nguồn gốc và hỏng một phần artefact.

Dự án hiện có 3 lớp chính:

- ứng dụng C user-space giữ tính tương thích với binary cũ
- ứng dụng desktop PyQt5 để thao tác bằng giao diện
- ứng dụng web Python chạy trên trình duyệt local

## Thành phần chính

- `student_mgmt`: chương trình C user-space
- `student_app.py`: ứng dụng desktop PyQt5
- `student_web.py`: ứng dụng web local
- `kb_driver`: khung kernel module phục dựng từ artefact còn sót lại

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
- `string_utils.c`, `string_utils.h`: chuẩn hóa chuỗi
- `student_app.py`: ứng dụng desktop
- `student_web.py`: ứng dụng web
- `common.h`: các hằng số và struct dùng chung

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

## Chạy ứng dụng web

Chạy:

```sh
python3 student_web.py
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

## Build kernel module

Cần Linux headers cho kernel đang chạy:

```sh
make -f Makefile.kmod
```

## Ghi chú

- Phần user-space C ban đầu được phục dựng để giữ hành vi gần với binary `demo_p1`
- `students.dat` được mở rộng để phục vụ desktop app và web app
- Repo hiện có cả source, file build và một số file dữ liệu runtime

## Giới hạn

- Một phần artefact gốc đã hỏng hoặc không còn đủ để phục dựng đầy đủ module kernel ban đầu
- Web app hiện chạy local, không phải một hệ thống production hardening
- Ứng dụng C user-space chưa được mở rộng đầy đủ UI/phân quyền như desktop app và web app

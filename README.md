# ProjectLinux

Ban phuc dung cua mot repo C/Linux bi mat source goc va hong mot phan artefact.

## Thanh phan

- `student_mgmt`: chuong trinh quan ly sinh vien chay user-space.
- `kb_driver`: khung kernel module phuc dung tu Kbuild con sot lai.

## Nhung gi da phuc dung

- Phan user-space duoc reverse tu binary `demo_p1`.
- Hanh vi menu, luong dang nhap va dinh dang `users.dat` duoc giu tuong thich voi binary cu.
- `students.dat` ho tro doc du lieu cu 3 truong va ghi du lieu mo rong cho desktop/web app.
- Ham `sha256_hex()` giu nguyen ten de tuong thich, nhung binary goc thuc te khong dung SHA-256.
  No dung hash 32-bit kieu FNV-1a roi lap thanh 64 ky tu hex.
- Kernel module goc khong con du artefact hop le de khoi phuc tinh nang. Repo nay chi dung lai khung `kb_driver`
  dua tren bang chung `obj-m := kb_driver.o` va `kb_driver-objs := driver/string_utils.o`.

## Cau truc du an

- `main.c`: menu va luong chuong trinh.
- `auth.c`: nap/luu user va xac thuc.
- `student.c`: nap/luu danh sach sinh vien.
- `sha256.c`: ham hash tuong thich voi binary cu.
- `string_utils.c`: chuan hoa chuoi cho phan user-space.
- `driver/string_utils.c`: module kernel scaffold.

## Build user-space

```sh
make
```

Chay:

```sh
./student_mgmt
```

Neu `users.dat` chua ton tai hoac khong doc duoc, chuong trinh tao mac dinh:

- username: `admin`
- password: `admin123`

## Dinh dang du lieu

### `users.dat`

File nhi phan gom cac ban ghi lap lai:

- 32 byte username
- 64 byte password hash

### `students.dat`

File text. Ban ghi cu van doc duoc theo 3 dong:

1. Ma SV
2. Ho va ten
3. Lop

Ban ghi moi duoc ghi voi header `STUDENT_V2` va 7 truong:

1. Ma SV
2. Ho va ten
3. Lop
4. Dia chi
5. So dien thoai
6. Nganh hoc
7. GPA

## Build kernel module

Can Linux headers cho kernel dang chay:

```sh
make -f Makefile.kmod
```

## Gioi han

- `README.md`, `Makefile`, `kb_driver.ko` va nhieu artefact goc da bi hong.
- Khong con du source/module goc de phuc dung dung chuc nang kernel ban dau.
- Ban phuc dung nay uu tien build lai duoc va giu tuong thich du lieu voi `demo_p1`.
# DriverLinux
# DriverLinux

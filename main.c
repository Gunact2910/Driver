#include "auth.h"
#include "sha256.h"
#include "student.h"
#include "string_utils.h"

#include <stdio.h>
#include <string.h>

#define USERS_FILE "users.dat"
#define STUDENTS_FILE "students.dat"

static void ensure_default_admin(User *users, char password_hashes[][PASSWORD_HASH_LEN], int *user_count) {
    char default_hash[PASSWORD_HASH_LEN] = {0};

    puts("Tao nguoi dung mac dinh admin/admin123");
    memcpy(users[0].username, "admin", 5);
    users[0].username[5] = '\0';
    sha256_hex("admin123", default_hash);
    memcpy(password_hashes[0], default_hash, PASSWORD_HASH_LEN - 1);
    password_hashes[0][PASSWORD_HASH_LEN - 1] = '\0';
    memcpy(users[0].password_hash, default_hash, PASSWORD_HASH_LEN - 1);
    users[0].password_hash[PASSWORD_HASH_LEN - 1] = '\0';
    *user_count = 1;
    save_users(USERS_FILE, users, password_hashes, *user_count);
}

int main(void) {
    User users[MAX_USERS] = {0};
    char password_hashes[MAX_USERS][PASSWORD_HASH_LEN] = {{0}};
    Student students[MAX_STUDENTS] = {0};
    int user_count = 0;
    int student_count = 0;
    int upgraded_legacy_hash = 0;
    char username[USERNAME_LEN] = {0};
    char password[128] = {0};

    if (!load_users(USERS_FILE, users, password_hashes, &user_count)) {
        ensure_default_admin(users, password_hashes, &user_count);
    }

    printf("Dang nhap: \n");
    printf("Username: ");
    if (fgets(username, sizeof(username), stdin) == NULL) {
        return 1;
    }
    username[strcspn(username, "\n")] = '\0';

    printf("Password: ");
    if (fgets(password, sizeof(password), stdin) == NULL) {
        return 1;
    }
    password[strcspn(password, "\n")] = '\0';

    if (!authenticate(username, password, users, password_hashes, user_count, &upgraded_legacy_hash)) {
        puts("Dang nhap that bai.");
        return 1;
    }

    puts("Dang nhap thanh cong.");
    if (upgraded_legacy_hash) {
        save_users(USERS_FILE, users, password_hashes, user_count);
        puts("Da nang cap users.dat sang SHA-256 chuan.");
    }
    load_students(STUDENTS_FILE, students, &student_count);

    for (;;) {
        int choice = 0;

        printf("Menu: 1) Them 2) Danh sach 3) Luu+Thoat\nLua chon: ");
        if (scanf("%d", &choice) != 1) {
            return 0;
        }
        getc(stdin);

        if (choice == 1) {
            Student *student;

            if (student_count > 255) {
                puts("Full");
                continue;
            }

            student = &students[student_count];

            printf("Ma SV: ");
            fgets(student->student_id, sizeof(student->student_id), stdin);
            student->student_id[strcspn(student->student_id, "\n")] = '\0';
            normalize_str(student->student_id);

            printf("Ho va ten: ");
            fgets(student->full_name, sizeof(student->full_name), stdin);
            student->full_name[strcspn(student->full_name, "\n")] = '\0';
            normalize_str(student->full_name);

            printf("Lop: ");
            fgets(student->class_name, sizeof(student->class_name), stdin);
            student->class_name[strcspn(student->class_name, "\n")] = '\0';
            normalize_str(student->class_name);

            ++student_count;
        } else if (choice == 2) {
            int i;

            printf("-- Danh sach sinh vien (%d) --\n", student_count);
            for (i = 0; i < student_count; ++i) {
                printf("%d. %s | %s | %s\n",
                       i + 1,
                       students[i].student_id,
                       students[i].full_name,
                       students[i].class_name);
            }
        } else if (choice == 3) {
            save_students(STUDENTS_FILE, students, student_count);
            printf("Da luu %d SV vao %s\n", student_count, STUDENTS_FILE);
            return 0;
        } else {
            puts("Lua chon khong hop le");
        }
    }
}

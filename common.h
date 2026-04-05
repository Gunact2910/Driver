#ifndef COMMON_H
#define COMMON_H

#include <stddef.h>

#define MAX_USERS 64
#define MAX_STUDENTS 256
#define USERNAME_LEN 32
#define PASSWORD_HASH_LEN 65
#define STUDENT_ID_LEN 32
#define STUDENT_NAME_LEN 128
#define STUDENT_CLASS_LEN 32
#define STUDENT_ADDRESS_LEN 256
#define STUDENT_PHONE_LEN 32
#define STUDENT_MAJOR_LEN 128
#define STUDENT_GPA_LEN 16

typedef struct {
    char username[USERNAME_LEN];
    char password_hash[PASSWORD_HASH_LEN];
} User;

typedef struct {
    char student_id[STUDENT_ID_LEN];
    char full_name[STUDENT_NAME_LEN];
    char class_name[STUDENT_CLASS_LEN];
    char address[STUDENT_ADDRESS_LEN];
    char phone[STUDENT_PHONE_LEN];
    char major[STUDENT_MAJOR_LEN];
    char gpa[STUDENT_GPA_LEN];
} Student;

#endif

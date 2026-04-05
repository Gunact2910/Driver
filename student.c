#include "student.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define STUDENT_FILE_HEADER "STUDENT_V2"

static void trim_newline(char *value) {
    value[strcspn(value, "\n")] = '\0';
}

static int read_line(FILE *fp, char *buffer, size_t size) {
    if (fgets(buffer, size, fp) == NULL) {
        return 0;
    }
    trim_newline(buffer);
    return 1;
}

int load_students(const char *path, Student *students, int *count) {
    FILE *fp;
    char first_line[64] = {0};

    *count = 0;
    fp = fopen(path, "r");
    if (fp == NULL) {
        return 0;
    }

    if (!read_line(fp, first_line, sizeof(first_line))) {
        fclose(fp);
        return 1;
    }

    if (strcmp(first_line, STUDENT_FILE_HEADER) == 0) {
        while (*count < MAX_STUDENTS) {
            Student *student = &students[*count];

            if (!read_line(fp, student->student_id, sizeof(student->student_id))) {
                break;
            }
            if (!read_line(fp, student->full_name, sizeof(student->full_name))) {
                break;
            }
            if (!read_line(fp, student->class_name, sizeof(student->class_name))) {
                break;
            }
            if (!read_line(fp, student->address, sizeof(student->address))) {
                break;
            }
            if (!read_line(fp, student->phone, sizeof(student->phone))) {
                break;
            }
            if (!read_line(fp, student->major, sizeof(student->major))) {
                break;
            }
            if (!read_line(fp, student->gpa, sizeof(student->gpa))) {
                break;
            }

            ++(*count);
        }

        fclose(fp);
        return 1;
    }

    do {
        Student *student = &students[*count];

        strncpy(student->student_id, first_line, sizeof(student->student_id) - 1);
        student->student_id[sizeof(student->student_id) - 1] = '\0';

        if (!read_line(fp, student->full_name, sizeof(student->full_name))) {
            break;
        }

        if (!read_line(fp, student->class_name, sizeof(student->class_name))) {
            break;
        }

        ++(*count);
    } while (*count < MAX_STUDENTS && read_line(fp, first_line, sizeof(first_line)));

    fclose(fp);
    return 1;
}

int save_students(const char *path, const Student *students, int count) {
    FILE *fp;
    int i;

    fp = fopen(path, "w");
    if (fp == NULL) {
        return 0;
    }

    fprintf(fp, "%s\n", STUDENT_FILE_HEADER);
    for (i = 0; i < count; ++i) {
        fprintf(fp,
                "%s\n%s\n%s\n%s\n%s\n%s\n%s\n",
                students[i].student_id,
                students[i].full_name,
                students[i].class_name,
                students[i].address,
                students[i].phone,
                students[i].major,
                students[i].gpa);
    }

    fclose(fp);
    return 1;
}

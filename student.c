#include "student.h"

#include <stdio.h>
#include <string.h>

int load_students(const char *path, Student *students, int *count) {
    FILE *fp;

    *count = 0;
    fp = fopen(path, "r");
    if (fp == NULL) {
        return 0;
    }

    while (*count < MAX_STUDENTS) {
        Student *student = &students[*count];

        if (fgets(student->student_id, sizeof(student->student_id), fp) == NULL) {
            break;
        }
        student->student_id[strcspn(student->student_id, "\n")] = '\0';

        if (fgets(student->full_name, sizeof(student->full_name), fp) == NULL) {
            break;
        }
        student->full_name[strcspn(student->full_name, "\n")] = '\0';

        if (fgets(student->class_name, sizeof(student->class_name), fp) == NULL) {
            break;
        }
        student->class_name[strcspn(student->class_name, "\n")] = '\0';

        ++(*count);
    }

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

    for (i = 0; i < count; ++i) {
        fprintf(fp, "%s\n%s\n%s\n", students[i].student_id, students[i].full_name, students[i].class_name);
    }

    fclose(fp);
    return 1;
}

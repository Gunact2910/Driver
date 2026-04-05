#ifndef STUDENT_H
#define STUDENT_H

#include "common.h"

int load_students(const char *path, Student *students, int *count);
int save_students(const char *path, const Student *students, int count);

#endif

#include "string_utils.h"

#include <ctype.h>

void normalize_str(char *str) {
    char *dst = str;

    while (*str != '\0') {
        unsigned char ch = (unsigned char)*str++;
        if (isspace(ch)) {
            continue;
        }
        *dst++ = (char)tolower(ch);
    }

    *dst = '\0';
}

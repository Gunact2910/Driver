#ifndef DRIVER_STRING_UTILS_SHARED_H
#define DRIVER_STRING_UTILS_SHARED_H

#include <stddef.h>

static inline size_t kb_normalize_ascii_impl(char *dst, const char *src)
{
    size_t written = 0;

    while (*src != '\0') {
        unsigned char ch = (unsigned char)*src++;

        if (ch == ' ' || ch == '\t' || ch == '\n' || ch == '\r' || ch == '\f' || ch == '\v') {
            continue;
        }
        if (ch >= 'A' && ch <= 'Z') {
            ch = (unsigned char)(ch - 'A' + 'a');
        }
        dst[written++] = (char)ch;
    }

    dst[written] = '\0';
    return written;
}

#endif

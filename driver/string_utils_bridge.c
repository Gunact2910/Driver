#include "string_utils_shared.h"

#include <stddef.h>

int kb_normalize_ascii_user(const char *src, char *dst, size_t dst_size)
{
    size_t written;

    if (src == NULL || dst == NULL || dst_size == 0) {
        return -1;
    }

    written = kb_normalize_ascii_impl(dst, src);
    if (written >= dst_size) {
        dst[0] = '\0';
        return -1;
    }

    return 0;
}

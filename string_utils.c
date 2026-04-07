#include "string_utils.h"
#include "driver/string_utils_shared.h"

void normalize_str(char *str) {
    kb_normalize_ascii_impl(str, str);
}

#ifndef SHA256_H
#define SHA256_H

#include <stddef.h>

void sha256_hex(const char *input, char *output);
void sha256_bytes(const void *data, size_t len, unsigned char *digest);

#endif

#include "auth.h"

#include "sha256.h"
#include "string_utils.h"

#include <stdint.h>
#include <stdio.h>
#include <string.h>

static void legacy_hash_hex(const char *input, char *output) {
    uint32_t hash = 0x811c9dc5u;
    size_t i;

    for (i = 0; i < strlen(input); ++i) {
        hash ^= (unsigned char)input[i];
        hash *= 0x01000193u;
    }

    sprintf(output,
            "%08x%08x%08x%08x%08x%08x%08x%08x",
            hash,
            hash >> 4,
            hash >> 8,
            hash >> 12,
            hash >> 16,
            hash >> 20,
            hash >> 24,
            hash >> 28);
}

int load_users(const char *path, User *users, char (*password_hashes)[PASSWORD_HASH_LEN], int *count) {
    FILE *fp;

    *count = 0;
    fp = fopen(path, "rb");
    if (fp == NULL) {
        return 0;
    }

    while (*count < MAX_USERS) {
        char username_chunk[USERNAME_LEN] = {0};
        char password_chunk[PASSWORD_HASH_LEN] = {0};

        if (fread(username_chunk, 1, USERNAME_LEN, fp) != USERNAME_LEN) {
            break;
        }
        if (fread(password_chunk, 1, PASSWORD_HASH_LEN - 1, fp) != PASSWORD_HASH_LEN - 1) {
            break;
        }
        if (username_chunk[0] == '\0') {
            continue;
        }

        memcpy(users[*count].username, username_chunk, USERNAME_LEN - 1);
        users[*count].username[USERNAME_LEN - 1] = '\0';
        memcpy(password_hashes[*count], password_chunk, PASSWORD_HASH_LEN - 1);
        password_hashes[*count][PASSWORD_HASH_LEN - 1] = '\0';
        memcpy(users[*count].password_hash, password_hashes[*count], PASSWORD_HASH_LEN - 1);
        users[*count].password_hash[PASSWORD_HASH_LEN - 1] = '\0';
        ++(*count);
    }

    fclose(fp);
    return *count > 0;
}

int save_users(const char *path, const User *users, const char (*password_hashes)[PASSWORD_HASH_LEN], int count) {
    FILE *fp;
    int i;

    fp = fopen(path, "wb");
    if (fp == NULL) {
        return 0;
    }

    for (i = 0; i < count; ++i) {
        char username_chunk[USERNAME_LEN] = {0};

        memcpy(username_chunk, users[i].username, USERNAME_LEN - 1);
        fwrite(username_chunk, 1, USERNAME_LEN, fp);
        fwrite(password_hashes[i], 1, PASSWORD_HASH_LEN - 1, fp);
    }

    fclose(fp);
    return 1;
}

int authenticate(const char *username,
                 const char *password,
                 User *users,
                 char (*password_hashes)[PASSWORD_HASH_LEN],
                 int count,
                 int *upgraded_legacy_hash) {
    char normalized_input[USERNAME_LEN] = {0};
    char computed_hash[PASSWORD_HASH_LEN] = {0};
    char legacy_hash[PASSWORD_HASH_LEN] = {0};
    int i;

    if (upgraded_legacy_hash != NULL) {
        *upgraded_legacy_hash = 0;
    }

    strncpy(normalized_input, username, USERNAME_LEN - 1);
    normalize_str(normalized_input);
    sha256_hex(password, computed_hash);
    legacy_hash_hex(password, legacy_hash);

    for (i = 0; i < count; ++i) {
        char normalized_user[USERNAME_LEN] = {0};

        strncpy(normalized_user, users[i].username, USERNAME_LEN - 1);
        normalize_str(normalized_user);
        if (strcmp(normalized_user, normalized_input) == 0) {
            if (strncmp(password_hashes[i], computed_hash, PASSWORD_HASH_LEN - 1) == 0) {
                return 1;
            }
            if (strncmp(password_hashes[i], legacy_hash, PASSWORD_HASH_LEN - 1) == 0) {
                memcpy(password_hashes[i], computed_hash, PASSWORD_HASH_LEN - 1);
                password_hashes[i][PASSWORD_HASH_LEN - 1] = '\0';
                memcpy(users[i].password_hash, computed_hash, PASSWORD_HASH_LEN - 1);
                users[i].password_hash[PASSWORD_HASH_LEN - 1] = '\0';
                if (upgraded_legacy_hash != NULL) {
                    *upgraded_legacy_hash = 1;
                }
                return 1;
            }
            return 0;
        }
    }

    return 0;
}

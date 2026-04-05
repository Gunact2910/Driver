#ifndef AUTH_H
#define AUTH_H

#include "common.h"

int load_users(const char *path, User *users, char (*password_hashes)[PASSWORD_HASH_LEN], int *count);
int save_users(const char *path, const User *users, const char (*password_hashes)[PASSWORD_HASH_LEN], int count);
int authenticate(const char *username,
                 const char *password,
                 User *users,
                 char (*password_hashes)[PASSWORD_HASH_LEN],
                 int count,
                 int *upgraded_legacy_hash);

#endif

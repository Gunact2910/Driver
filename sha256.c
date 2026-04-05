#include "sha256.h"

#include <stdint.h>
#include <string.h>

#include <stdio.h>

#define SHA256_BLOCK_SIZE 64
#define SHA256_DIGEST_SIZE 32

typedef struct {
    uint32_t state[8];
    uint64_t bit_len;
    unsigned char buffer[SHA256_BLOCK_SIZE];
    size_t buffer_len;
} Sha256Ctx;

static const uint32_t k_sha256_round_constants[64] = {
    0x428a2f98u, 0x71374491u, 0xb5c0fbcfu, 0xe9b5dba5u,
    0x3956c25bu, 0x59f111f1u, 0x923f82a4u, 0xab1c5ed5u,
    0xd807aa98u, 0x12835b01u, 0x243185beu, 0x550c7dc3u,
    0x72be5d74u, 0x80deb1feu, 0x9bdc06a7u, 0xc19bf174u,
    0xe49b69c1u, 0xefbe4786u, 0x0fc19dc6u, 0x240ca1ccu,
    0x2de92c6fu, 0x4a7484aau, 0x5cb0a9dcu, 0x76f988dau,
    0x983e5152u, 0xa831c66du, 0xb00327c8u, 0xbf597fc7u,
    0xc6e00bf3u, 0xd5a79147u, 0x06ca6351u, 0x14292967u,
    0x27b70a85u, 0x2e1b2138u, 0x4d2c6dfcu, 0x53380d13u,
    0x650a7354u, 0x766a0abbu, 0x81c2c92eu, 0x92722c85u,
    0xa2bfe8a1u, 0xa81a664bu, 0xc24b8b70u, 0xc76c51a3u,
    0xd192e819u, 0xd6990624u, 0xf40e3585u, 0x106aa070u,
    0x19a4c116u, 0x1e376c08u, 0x2748774cu, 0x34b0bcb5u,
    0x391c0cb3u, 0x4ed8aa4au, 0x5b9cca4fu, 0x682e6ff3u,
    0x748f82eeu, 0x78a5636fu, 0x84c87814u, 0x8cc70208u,
    0x90befffau, 0xa4506cebu, 0xbef9a3f7u, 0xc67178f2u,
};

static uint32_t rotr32(uint32_t value, unsigned int bits) {
    return (value >> bits) | (value << (32 - bits));
}

static uint32_t choose32(uint32_t x, uint32_t y, uint32_t z) {
    return (x & y) ^ (~x & z);
}

static uint32_t majority32(uint32_t x, uint32_t y, uint32_t z) {
    return (x & y) ^ (x & z) ^ (y & z);
}

static uint32_t big_sigma0(uint32_t x) {
    return rotr32(x, 2) ^ rotr32(x, 13) ^ rotr32(x, 22);
}

static uint32_t big_sigma1(uint32_t x) {
    return rotr32(x, 6) ^ rotr32(x, 11) ^ rotr32(x, 25);
}

static uint32_t small_sigma0(uint32_t x) {
    return rotr32(x, 7) ^ rotr32(x, 18) ^ (x >> 3);
}

static uint32_t small_sigma1(uint32_t x) {
    return rotr32(x, 17) ^ rotr32(x, 19) ^ (x >> 10);
}

static void sha256_transform(Sha256Ctx *ctx, const unsigned char block[SHA256_BLOCK_SIZE]) {
    uint32_t schedule[64];
    uint32_t a;
    uint32_t b;
    uint32_t c;
    uint32_t d;
    uint32_t e;
    uint32_t f;
    uint32_t g;
    uint32_t h;
    size_t i;

    for (i = 0; i < 16; ++i) {
        size_t offset = i * 4;

        schedule[i] = ((uint32_t)block[offset] << 24)
                    | ((uint32_t)block[offset + 1] << 16)
                    | ((uint32_t)block[offset + 2] << 8)
                    | (uint32_t)block[offset + 3];
    }
    for (i = 16; i < 64; ++i) {
        schedule[i] = small_sigma1(schedule[i - 2])
                    + schedule[i - 7]
                    + small_sigma0(schedule[i - 15])
                    + schedule[i - 16];
    }

    a = ctx->state[0];
    b = ctx->state[1];
    c = ctx->state[2];
    d = ctx->state[3];
    e = ctx->state[4];
    f = ctx->state[5];
    g = ctx->state[6];
    h = ctx->state[7];

    for (i = 0; i < 64; ++i) {
        uint32_t temp1 = h + big_sigma1(e) + choose32(e, f, g) + k_sha256_round_constants[i] + schedule[i];
        uint32_t temp2 = big_sigma0(a) + majority32(a, b, c);

        h = g;
        g = f;
        f = e;
        e = d + temp1;
        d = c;
        c = b;
        b = a;
        a = temp1 + temp2;
    }

    ctx->state[0] += a;
    ctx->state[1] += b;
    ctx->state[2] += c;
    ctx->state[3] += d;
    ctx->state[4] += e;
    ctx->state[5] += f;
    ctx->state[6] += g;
    ctx->state[7] += h;
}

static void sha256_init(Sha256Ctx *ctx) {
    ctx->state[0] = 0x6a09e667u;
    ctx->state[1] = 0xbb67ae85u;
    ctx->state[2] = 0x3c6ef372u;
    ctx->state[3] = 0xa54ff53au;
    ctx->state[4] = 0x510e527fu;
    ctx->state[5] = 0x9b05688cu;
    ctx->state[6] = 0x1f83d9abu;
    ctx->state[7] = 0x5be0cd19u;
    ctx->bit_len = 0;
    ctx->buffer_len = 0;
}

static void sha256_update(Sha256Ctx *ctx, const unsigned char *data, size_t len) {
    size_t i;

    for (i = 0; i < len; ++i) {
        ctx->buffer[ctx->buffer_len++] = data[i];
        if (ctx->buffer_len == SHA256_BLOCK_SIZE) {
            sha256_transform(ctx, ctx->buffer);
            ctx->bit_len += SHA256_BLOCK_SIZE * 8u;
            ctx->buffer_len = 0;
        }
    }
}

static void sha256_final(Sha256Ctx *ctx, unsigned char digest[SHA256_DIGEST_SIZE]) {
    size_t i;

    ctx->bit_len += (uint64_t)ctx->buffer_len * 8u;
    ctx->buffer[ctx->buffer_len++] = 0x80u;

    if (ctx->buffer_len > 56) {
        while (ctx->buffer_len < SHA256_BLOCK_SIZE) {
            ctx->buffer[ctx->buffer_len++] = 0;
        }
        sha256_transform(ctx, ctx->buffer);
        ctx->buffer_len = 0;
    }

    while (ctx->buffer_len < 56) {
        ctx->buffer[ctx->buffer_len++] = 0;
    }

    for (i = 0; i < 8; ++i) {
        ctx->buffer[56 + i] = (unsigned char)(ctx->bit_len >> (56 - i * 8));
    }
    sha256_transform(ctx, ctx->buffer);

    for (i = 0; i < 8; ++i) {
        digest[i * 4] = (unsigned char)(ctx->state[i] >> 24);
        digest[i * 4 + 1] = (unsigned char)(ctx->state[i] >> 16);
        digest[i * 4 + 2] = (unsigned char)(ctx->state[i] >> 8);
        digest[i * 4 + 3] = (unsigned char)ctx->state[i];
    }
}

void sha256_bytes(const void *data, size_t len, unsigned char *digest) {
    Sha256Ctx ctx;

    sha256_init(&ctx);
    sha256_update(&ctx, (const unsigned char *)data, len);
    sha256_final(&ctx, digest);
}

void sha256_hex(const char *input, char *output) {
    unsigned char digest[SHA256_DIGEST_SIZE];
    size_t i;

    sha256_bytes(input, strlen(input), digest);
    for (i = 0; i < SHA256_DIGEST_SIZE; ++i) {
        sprintf(output + (i * 2), "%02x", digest[i]);
    }
    output[SHA256_DIGEST_SIZE * 2] = '\0';
}

#include <linux/ctype.h>
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/module.h>

#include "string_utils_shared.h"

size_t kb_normalize_ascii(char *dst, const char *src)
{
    return kb_normalize_ascii_impl(dst, src);
}
EXPORT_SYMBOL_GPL(kb_normalize_ascii);

static int __init kb_driver_init(void)
{
    char sample[32];

    kb_normalize_ascii(sample, " Kernel Driver Skeleton ");
    pr_info("kb_driver: loaded, sample='%s'\n", sample);
    return 0;
}

static void __exit kb_driver_exit(void)
{
    pr_info("kb_driver: unloaded\n");
}

module_init(kb_driver_init);
module_exit(kb_driver_exit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Codex reconstruction");
MODULE_DESCRIPTION("Reconstructed kb_driver skeleton from surviving Kbuild artefacts");

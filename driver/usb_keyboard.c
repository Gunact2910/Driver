#include <linux/bitops.h>
#include <linux/hid.h>
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/proc_fs.h>
#include <linux/seq_file.h>
#include <linux/slab.h>
#include <linux/spinlock.h>
#include <linux/timekeeping.h>
#include <linux/uaccess.h>
#include <linux/usb.h>

#define KB_REPORT_SIZE 8
#define KB_KEYCODE_OFFSET 2
#define KB_KEYCODE_COUNT 6
#define KB_HISTORY_SIZE 128
#define KB_MAX_TRACKED_DEVICES 8
#define KB_IFACE_NAME_LEN 32
#define KB_ACTION_NAME_LEN 10
#define KB_PROC_NAME "kb_driver"

struct kb_device {
    struct usb_device *udev;
    struct usb_interface *interface;
    struct urb *irq_urb;
    unsigned char *irq_buf;
    dma_addr_t irq_dma;
    unsigned char prev_report[KB_REPORT_SIZE];
    char iface_name[KB_IFACE_NAME_LEN];
    int monitor_slot;
};

struct kb_event {
    u64 seq;
    u64 timestamp_ms;
    unsigned char code;
    unsigned char pressed;
    char iface[KB_IFACE_NAME_LEN];
};

struct kb_device_state {
    bool active;
    char iface[KB_IFACE_NAME_LEN];
    u16 vendor_id;
    u16 product_id;
};

struct kb_monitor_state {
    spinlock_t lock;
    bool logging_enabled;
    u64 next_seq;
    u64 total_press_events;
    u64 total_release_events;
    u32 key_press_counts[256];
    u32 key_release_counts[256];
    unsigned int history_head;
    unsigned int history_count;
    struct kb_event history[KB_HISTORY_SIZE];
    struct kb_device_state devices[KB_MAX_TRACKED_DEVICES];
};

struct kb_monitor_snapshot {
    bool logging_enabled;
    u64 total_press_events;
    u64 total_release_events;
    unsigned int history_head;
    unsigned int history_count;
    u32 key_press_counts[256];
    u32 key_release_counts[256];
    struct kb_event history[KB_HISTORY_SIZE];
    struct kb_device_state devices[KB_MAX_TRACKED_DEVICES];
};

static struct proc_dir_entry *kb_proc_entry;
static struct kb_monitor_state kb_monitor = {
    .lock = __SPIN_LOCK_UNLOCKED(kb_monitor.lock),
    .logging_enabled = true,
};

static const char *const kb_modifier_names[8] = {
    "LeftCtrl",
    "LeftShift",
    "LeftAlt",
    "LeftMeta",
    "RightCtrl",
    "RightShift",
    "RightAlt",
    "RightMeta",
};

static int kb_report_contains(const unsigned char *report, unsigned char code)
{
    int i;

    for (i = 0; i < KB_KEYCODE_COUNT; ++i) {
        if (report[KB_KEYCODE_OFFSET + i] == code) {
            return 1;
        }
    }
    return 0;
}

static const char *kb_usage_name(unsigned char code)
{
    if (code >= 0xe0 && code <= 0xe7) {
        return kb_modifier_names[code - 0xe0];
    }

    switch (code) {
    case 0x04: return "A";
    case 0x05: return "B";
    case 0x06: return "C";
    case 0x07: return "D";
    case 0x08: return "E";
    case 0x09: return "F";
    case 0x0a: return "G";
    case 0x0b: return "H";
    case 0x0c: return "I";
    case 0x0d: return "J";
    case 0x0e: return "K";
    case 0x0f: return "L";
    case 0x10: return "M";
    case 0x11: return "N";
    case 0x12: return "O";
    case 0x13: return "P";
    case 0x14: return "Q";
    case 0x15: return "R";
    case 0x16: return "S";
    case 0x17: return "T";
    case 0x18: return "U";
    case 0x19: return "V";
    case 0x1a: return "W";
    case 0x1b: return "X";
    case 0x1c: return "Y";
    case 0x1d: return "Z";
    case 0x1e: return "1";
    case 0x1f: return "2";
    case 0x20: return "3";
    case 0x21: return "4";
    case 0x22: return "5";
    case 0x23: return "6";
    case 0x24: return "7";
    case 0x25: return "8";
    case 0x26: return "9";
    case 0x27: return "0";
    case 0x28: return "Enter";
    case 0x29: return "Esc";
    case 0x2a: return "Backspace";
    case 0x2b: return "Tab";
    case 0x2c: return "Space";
    case 0x2d: return "-";
    case 0x2e: return "=";
    case 0x2f: return "[";
    case 0x30: return "]";
    case 0x31: return "\\";
    case 0x33: return ";";
    case 0x34: return "'";
    case 0x35: return "`";
    case 0x36: return ",";
    case 0x37: return ".";
    case 0x38: return "/";
    case 0x39: return "CapsLock";
    case 0x3a: return "F1";
    case 0x3b: return "F2";
    case 0x3c: return "F3";
    case 0x3d: return "F4";
    case 0x3e: return "F5";
    case 0x3f: return "F6";
    case 0x40: return "F7";
    case 0x41: return "F8";
    case 0x42: return "F9";
    case 0x43: return "F10";
    case 0x44: return "F11";
    case 0x45: return "F12";
    case 0x46: return "PrintScreen";
    case 0x47: return "ScrollLock";
    case 0x48: return "Pause";
    case 0x49: return "Insert";
    case 0x4a: return "Home";
    case 0x4b: return "PageUp";
    case 0x4c: return "Delete";
    case 0x4d: return "End";
    case 0x4e: return "PageDown";
    case 0x4f: return "Right";
    case 0x50: return "Left";
    case 0x51: return "Down";
    case 0x52: return "Up";
    case 0x53: return "NumLock";
    case 0x54: return "Keypad /";
    case 0x55: return "Keypad *";
    case 0x56: return "Keypad -";
    case 0x57: return "Keypad +";
    case 0x58: return "Keypad Enter";
    case 0x59: return "Keypad 1";
    case 0x5a: return "Keypad 2";
    case 0x5b: return "Keypad 3";
    case 0x5c: return "Keypad 4";
    case 0x5d: return "Keypad 5";
    case 0x5e: return "Keypad 6";
    case 0x5f: return "Keypad 7";
    case 0x60: return "Keypad 8";
    case 0x61: return "Keypad 9";
    case 0x62: return "Keypad 0";
    case 0x63: return "Keypad .";
    default: return NULL;
    }
}

static void kb_record_event(struct kb_device *kb, const char *action, unsigned char code, bool pressed)
{
    struct kb_event *event;
    unsigned long flags;
    struct timespec64 ts;

    spin_lock_irqsave(&kb_monitor.lock, flags);
    if (pressed) {
        kb_monitor.total_press_events++;
        kb_monitor.key_press_counts[code]++;
    } else {
        kb_monitor.total_release_events++;
        kb_monitor.key_release_counts[code]++;
    }

    if (!kb_monitor.logging_enabled) {
        spin_unlock_irqrestore(&kb_monitor.lock, flags);
        return;
    }

    ktime_get_real_ts64(&ts);
    event = &kb_monitor.history[kb_monitor.history_head];
    memset(event, 0, sizeof(*event));
    event->seq = ++kb_monitor.next_seq;
    event->timestamp_ms = ts.tv_sec * 1000ULL + ts.tv_nsec / 1000000ULL;
    event->code = code;
    event->pressed = pressed ? 1 : 0;
    strscpy(event->iface, kb->iface_name, sizeof(event->iface));

    kb_monitor.history_head = (kb_monitor.history_head + 1) % KB_HISTORY_SIZE;
    if (kb_monitor.history_count < KB_HISTORY_SIZE) {
        kb_monitor.history_count++;
    }
    spin_unlock_irqrestore(&kb_monitor.lock, flags);

    if (kb_usage_name(code) != NULL) {
        dev_info(&kb->interface->dev, "%s key %s (usage=0x%02x)\n", action, kb_usage_name(code), code);
    } else {
        dev_info(&kb->interface->dev, "%s key usage=0x%02x\n", action, code);
    }
}

static void kb_log_modifiers(struct kb_device *kb, const unsigned char *report)
{
    unsigned char changed = kb->prev_report[0] ^ report[0];
    int bit;

    for (bit = 0; bit < 8; ++bit) {
        if (changed & BIT(bit)) {
            bool pressed = (report[0] & BIT(bit)) != 0;

            kb_record_event(kb, pressed ? "pressed" : "released", 0xe0 + bit, pressed);
        }
    }
}

static void kb_log_keys(struct kb_device *kb, const unsigned char *report)
{
    int i;

    for (i = 0; i < KB_KEYCODE_COUNT; ++i) {
        unsigned char code = report[KB_KEYCODE_OFFSET + i];

        if (code == 0 || code == 1) {
            continue;
        }
        if (!kb_report_contains(kb->prev_report, code)) {
            kb_record_event(kb, "pressed", code, true);
        }
    }

    for (i = 0; i < KB_KEYCODE_COUNT; ++i) {
        unsigned char code = kb->prev_report[KB_KEYCODE_OFFSET + i];

        if (code == 0 || code == 1) {
            continue;
        }
        if (!kb_report_contains(report, code)) {
            kb_record_event(kb, "released", code, false);
        }
    }
}

static void kb_irq(struct urb *urb)
{
    struct kb_device *kb = urb->context;
    int ret;

    switch (urb->status) {
    case 0:
        kb_log_modifiers(kb, kb->irq_buf);
        kb_log_keys(kb, kb->irq_buf);
        memcpy(kb->prev_report, kb->irq_buf, KB_REPORT_SIZE);
        break;
    case -ECONNRESET:
    case -ENOENT:
    case -ESHUTDOWN:
    case -EPROTO:
        return;
    default:
        dev_warn(&kb->interface->dev, "interrupt urb status=%d\n", urb->status);
        break;
    }

    ret = usb_submit_urb(kb->irq_urb, GFP_ATOMIC);
    if (ret != 0) {
        dev_err(&kb->interface->dev, "failed to resubmit irq urb: %d\n", ret);
    }
}

static int kb_find_interrupt_endpoint(struct usb_host_interface *iface_desc,
                                      struct usb_endpoint_descriptor **endpoint)
{
    int i;

    for (i = 0; i < iface_desc->desc.bNumEndpoints; ++i) {
        struct usb_endpoint_descriptor *candidate = &iface_desc->endpoint[i].desc;

        if (usb_endpoint_is_int_in(candidate)) {
            *endpoint = candidate;
            return 0;
        }
    }

    return -ENODEV;
}

static int kb_alloc_monitor_slot(struct kb_device *kb)
{
    unsigned long flags;
    int slot;

    kb->monitor_slot = -1;
    spin_lock_irqsave(&kb_monitor.lock, flags);
    for (slot = 0; slot < KB_MAX_TRACKED_DEVICES; ++slot) {
        struct kb_device_state *state = &kb_monitor.devices[slot];

        if (state->active) {
            continue;
        }

        state->active = true;
        strscpy(state->iface, kb->iface_name, sizeof(state->iface));
        state->vendor_id = le16_to_cpu(kb->udev->descriptor.idVendor);
        state->product_id = le16_to_cpu(kb->udev->descriptor.idProduct);
        kb->monitor_slot = slot;
        break;
    }
    spin_unlock_irqrestore(&kb_monitor.lock, flags);

    return kb->monitor_slot >= 0 ? 0 : -ENOSPC;
}

static void kb_release_monitor_slot(struct kb_device *kb)
{
    unsigned long flags;

    if (kb->monitor_slot < 0 || kb->monitor_slot >= KB_MAX_TRACKED_DEVICES) {
        return;
    }

    spin_lock_irqsave(&kb_monitor.lock, flags);
    memset(&kb_monitor.devices[kb->monitor_slot], 0, sizeof(kb_monitor.devices[kb->monitor_slot]));
    spin_unlock_irqrestore(&kb_monitor.lock, flags);
    kb->monitor_slot = -1;
}

static int kb_driver_probe(struct usb_interface *interface, const struct usb_device_id *id)
{
    struct usb_device *udev = interface_to_usbdev(interface);
    struct usb_host_interface *iface_desc = interface->cur_altsetting;
    struct usb_endpoint_descriptor *irq_endpoint = NULL;
    struct kb_device *kb;
    unsigned int pipe;
    unsigned int interval;
    int ret;

    ret = kb_find_interrupt_endpoint(iface_desc, &irq_endpoint);
    if (ret != 0) {
        dev_err(&interface->dev, "no interrupt-in endpoint found\n");
        return ret;
    }

    kb = kzalloc(sizeof(*kb), GFP_KERNEL);
    if (kb == NULL) {
        return -ENOMEM;
    }

    kb->udev = usb_get_dev(udev);
    kb->interface = interface;
    kb->monitor_slot = -1;
    snprintf(kb->iface_name, sizeof(kb->iface_name), "%s:%u.%u",
             dev_name(&udev->dev),
             iface_desc->desc.bInterfaceNumber,
             iface_desc->desc.bAlternateSetting);
    usb_set_intfdata(interface, kb);

    ret = kb_alloc_monitor_slot(kb);
    if (ret != 0) {
        dev_warn(&interface->dev, "monitor slots exhausted, continuing without dashboard slot\n");
    }

    kb->irq_buf = usb_alloc_coherent(udev, KB_REPORT_SIZE, GFP_KERNEL, &kb->irq_dma);
    if (kb->irq_buf == NULL) {
        ret = -ENOMEM;
        goto err_free_device;
    }

    kb->irq_urb = usb_alloc_urb(0, GFP_KERNEL);
    if (kb->irq_urb == NULL) {
        ret = -ENOMEM;
        goto err_free_buffer;
    }

    ret = usb_control_msg(udev,
                          usb_sndctrlpipe(udev, 0),
                          0x0b,
                          USB_TYPE_CLASS | USB_RECIP_INTERFACE,
                          0,
                          iface_desc->desc.bInterfaceNumber,
                          NULL,
                          0,
                          USB_CTRL_SET_TIMEOUT);
    if (ret < 0) {
        dev_warn(&interface->dev, "failed to set boot protocol: %d\n", ret);
    }

    pipe = usb_rcvintpipe(udev, irq_endpoint->bEndpointAddress);
    interval = irq_endpoint->bInterval;
    usb_fill_int_urb(kb->irq_urb,
                     udev,
                     pipe,
                     kb->irq_buf,
                     KB_REPORT_SIZE,
                     kb_irq,
                     kb,
                     interval);
    kb->irq_urb->transfer_dma = kb->irq_dma;
    kb->irq_urb->transfer_flags |= URB_NO_TRANSFER_DMA_MAP;

    ret = usb_submit_urb(kb->irq_urb, GFP_KERNEL);
    if (ret != 0) {
        dev_err(&interface->dev, "failed to submit irq urb: %d\n", ret);
        goto err_free_urb;
    }

    dev_info(&interface->dev,
             "USB keyboard attached iface=%s vid=0x%04x pid=0x%04x endpoint=0x%02x interval=%u\n",
             kb->iface_name,
             le16_to_cpu(udev->descriptor.idVendor),
             le16_to_cpu(udev->descriptor.idProduct),
             irq_endpoint->bEndpointAddress,
             interval);
    dev_info(&interface->dev,
             "dashboard data available at /proc/%s\n",
             KB_PROC_NAME);
    return 0;

err_free_urb:
    usb_free_urb(kb->irq_urb);
err_free_buffer:
    usb_free_coherent(udev, KB_REPORT_SIZE, kb->irq_buf, kb->irq_dma);
err_free_device:
    kb_release_monitor_slot(kb);
    usb_set_intfdata(interface, NULL);
    usb_put_dev(kb->udev);
    kfree(kb);
    return ret;
}

static void kb_driver_disconnect(struct usb_interface *interface)
{
    struct kb_device *kb = usb_get_intfdata(interface);

    usb_set_intfdata(interface, NULL);
    if (kb == NULL) {
        return;
    }

    usb_kill_urb(kb->irq_urb);
    usb_free_urb(kb->irq_urb);
    usb_free_coherent(kb->udev, KB_REPORT_SIZE, kb->irq_buf, kb->irq_dma);
    kb_release_monitor_slot(kb);
    dev_info(&interface->dev, "USB keyboard disconnected iface=%s\n", kb->iface_name);
    usb_put_dev(kb->udev);
    kfree(kb);
}

static int kb_monitor_snapshot(struct kb_monitor_snapshot *snapshot)
{
    unsigned long flags;

    if (snapshot == NULL) {
        return -EINVAL;
    }

    memset(snapshot, 0, sizeof(*snapshot));
    spin_lock_irqsave(&kb_monitor.lock, flags);
    snapshot->logging_enabled = kb_monitor.logging_enabled;
    snapshot->total_press_events = kb_monitor.total_press_events;
    snapshot->total_release_events = kb_monitor.total_release_events;
    snapshot->history_head = kb_monitor.history_head;
    snapshot->history_count = kb_monitor.history_count;
    memcpy(snapshot->key_press_counts, kb_monitor.key_press_counts, sizeof(snapshot->key_press_counts));
    memcpy(snapshot->key_release_counts, kb_monitor.key_release_counts, sizeof(snapshot->key_release_counts));
    memcpy(snapshot->history, kb_monitor.history, sizeof(snapshot->history));
    memcpy(snapshot->devices, kb_monitor.devices, sizeof(snapshot->devices));
    spin_unlock_irqrestore(&kb_monitor.lock, flags);

    return 0;
}

static int kb_proc_show(struct seq_file *m, void *v)
{
    struct kb_monitor_snapshot *snapshot;
    int i;
    int active_devices = 0;

    snapshot = kzalloc(sizeof(*snapshot), GFP_KERNEL);
    if (snapshot == NULL) {
        return -ENOMEM;
    }

    kb_monitor_snapshot(snapshot);

    for (i = 0; i < KB_MAX_TRACKED_DEVICES; ++i) {
        if (snapshot->devices[i].active) {
            active_devices++;
        }
    }

    seq_puts(m, "[kb_driver]\n");
    seq_printf(m, "logging_enabled=%u\n", snapshot->logging_enabled ? 1 : 0);
    seq_printf(m, "active_devices=%d\n", active_devices);
    seq_printf(m, "total_press_events=%llu\n", snapshot->total_press_events);
    seq_printf(m, "total_release_events=%llu\n", snapshot->total_release_events);
    seq_printf(m, "history_entries=%u\n", snapshot->history_count);

    seq_puts(m, "\n[devices]\n");
    for (i = 0; i < KB_MAX_TRACKED_DEVICES; ++i) {
        if (!snapshot->devices[i].active) {
            continue;
        }

        seq_printf(m,
                   "%s|0x%04x|0x%04x\n",
                   snapshot->devices[i].iface,
                   snapshot->devices[i].vendor_id,
                   snapshot->devices[i].product_id);
    }

    seq_puts(m, "\n[history]\n");
    if (snapshot->history_count > 0) {
        unsigned int start = (snapshot->history_head + KB_HISTORY_SIZE - snapshot->history_count) % KB_HISTORY_SIZE;
        unsigned int index;

        for (i = 0; i < snapshot->history_count; ++i) {
            const struct kb_event *event = &snapshot->history[(start + i) % KB_HISTORY_SIZE];
            const char *name = kb_usage_name(event->code);

            index = (start + i) % KB_HISTORY_SIZE;
            if (index >= KB_HISTORY_SIZE) {
                continue;
            }
            seq_printf(m,
                       "%llu|%llu|%s|%s|%s|0x%02x\n",
                       event->seq,
                       event->timestamp_ms,
                       event->iface,
                       event->pressed ? "pressed" : "released",
                       name != NULL ? name : "Unknown",
                       event->code);
        }
    }

    seq_puts(m, "\n[key_stats]\n");
    for (i = 0; i < 256; ++i) {
        const char *name;

        if (snapshot->key_press_counts[i] == 0 && snapshot->key_release_counts[i] == 0) {
            continue;
        }

        name = kb_usage_name(i);
        seq_printf(m,
                   "0x%02x|%s|%u|%u\n",
                   i,
                   name != NULL ? name : "Unknown",
                   snapshot->key_press_counts[i],
                   snapshot->key_release_counts[i]);
    }

    kfree(snapshot);
    return 0;
}

static int kb_proc_open(struct inode *inode, struct file *file)
{
    return single_open(file, kb_proc_show, NULL);
}

static ssize_t kb_proc_write(struct file *file, const char __user *buffer, size_t count, loff_t *ppos)
{
    char command[32] = {0};
    unsigned long flags;
    size_t copied = min(count, sizeof(command) - 1);

    if (copy_from_user(command, buffer, copied) != 0) {
        return -EFAULT;
    }

    strim(command);
    spin_lock_irqsave(&kb_monitor.lock, flags);
    if (strcmp(command, "clear_history") == 0) {
        kb_monitor.history_head = 0;
        kb_monitor.history_count = 0;
        memset(kb_monitor.history, 0, sizeof(kb_monitor.history));
    } else if (strcmp(command, "reset_stats") == 0) {
        kb_monitor.next_seq = 0;
        kb_monitor.history_head = 0;
        kb_monitor.history_count = 0;
        kb_monitor.total_press_events = 0;
        kb_monitor.total_release_events = 0;
        memset(kb_monitor.history, 0, sizeof(kb_monitor.history));
        memset(kb_monitor.key_press_counts, 0, sizeof(kb_monitor.key_press_counts));
        memset(kb_monitor.key_release_counts, 0, sizeof(kb_monitor.key_release_counts));
    } else if (strcmp(command, "logging=1") == 0) {
        kb_monitor.logging_enabled = true;
    } else if (strcmp(command, "logging=0") == 0) {
        kb_monitor.logging_enabled = false;
    } else {
        spin_unlock_irqrestore(&kb_monitor.lock, flags);
        return -EINVAL;
    }
    spin_unlock_irqrestore(&kb_monitor.lock, flags);

    return count;
}

static const struct proc_ops kb_proc_ops = {
    .proc_open = kb_proc_open,
    .proc_read = seq_read,
    .proc_lseek = seq_lseek,
    .proc_release = single_release,
    .proc_write = kb_proc_write,
};

static const struct usb_device_id kb_driver_table[] = {
    { USB_INTERFACE_INFO(USB_INTERFACE_CLASS_HID, USB_INTERFACE_SUBCLASS_BOOT, USB_INTERFACE_PROTOCOL_KEYBOARD) },
    { }
};
MODULE_DEVICE_TABLE(usb, kb_driver_table);

static struct usb_driver kb_driver = {
    .name = "kb_driver",
    .probe = kb_driver_probe,
    .disconnect = kb_driver_disconnect,
    .id_table = kb_driver_table,
};

static int __init kb_driver_init(void)
{
    int ret;

    kb_proc_entry = proc_create(KB_PROC_NAME, 0666, NULL, &kb_proc_ops);
    if (kb_proc_entry == NULL) {
        return -ENOMEM;
    }

    ret = usb_register(&kb_driver);
    if (ret != 0) {
        proc_remove(kb_proc_entry);
        kb_proc_entry = NULL;
        return ret;
    }

    pr_info("kb_driver: control/status available at /proc/%s\n", KB_PROC_NAME);
    return 0;
}

static void __exit kb_driver_exit(void)
{
    usb_deregister(&kb_driver);
    if (kb_proc_entry != NULL) {
        proc_remove(kb_proc_entry);
        kb_proc_entry = NULL;
    }
}

module_init(kb_driver_init);
module_exit(kb_driver_exit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Codex reconstruction");
MODULE_DESCRIPTION("USB boot keyboard driver with dashboard-friendly proc interface");

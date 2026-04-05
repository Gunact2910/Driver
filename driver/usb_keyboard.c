#include <linux/bitops.h>
#include <linux/hid.h>
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/slab.h>
#include <linux/usb.h>

#define KB_REPORT_SIZE 8
#define KB_KEYCODE_OFFSET 2
#define KB_KEYCODE_COUNT 6

struct kb_device {
    struct usb_device *udev;
    struct usb_interface *interface;
    struct urb *irq_urb;
    unsigned char *irq_buf;
    dma_addr_t irq_dma;
    unsigned char prev_report[KB_REPORT_SIZE];
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

static int kb_report_contains(const unsigned char *report, unsigned char code) {
    int i;

    for (i = 0; i < KB_KEYCODE_COUNT; ++i) {
        if (report[KB_KEYCODE_OFFSET + i] == code) {
            return 1;
        }
    }
    return 0;
}

static const char *kb_usage_name(unsigned char code) {
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

static void kb_log_transition(struct usb_interface *interface,
                              const char *action,
                              unsigned char code) {
    const char *name = kb_usage_name(code);

    if (name != NULL) {
        dev_info(&interface->dev, "%s key %s (usage=0x%02x)\n", action, name, code);
    } else {
        dev_info(&interface->dev, "%s key usage=0x%02x\n", action, code);
    }
}

static void kb_log_modifiers(struct kb_device *kb, const unsigned char *report) {
    unsigned char changed = kb->prev_report[0] ^ report[0];
    int bit;

    for (bit = 0; bit < 8; ++bit) {
        if (changed & BIT(bit)) {
            const char *action = (report[0] & BIT(bit)) ? "pressed" : "released";

            dev_info(&kb->interface->dev, "%s modifier %s\n", action, kb_modifier_names[bit]);
        }
    }
}

static void kb_log_keys(struct kb_device *kb, const unsigned char *report) {
    int i;

    for (i = 0; i < KB_KEYCODE_COUNT; ++i) {
        unsigned char code = report[KB_KEYCODE_OFFSET + i];

        if (code == 0 || code == 1) {
            continue;
        }
        if (!kb_report_contains(kb->prev_report, code)) {
            kb_log_transition(kb->interface, "pressed", code);
        }
    }

    for (i = 0; i < KB_KEYCODE_COUNT; ++i) {
        unsigned char code = kb->prev_report[KB_KEYCODE_OFFSET + i];

        if (code == 0 || code == 1) {
            continue;
        }
        if (!kb_report_contains(report, code)) {
            kb_log_transition(kb->interface, "released", code);
        }
    }
}

static void kb_irq(struct urb *urb) {
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
                                      struct usb_endpoint_descriptor **endpoint) {
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

static int kb_driver_probe(struct usb_interface *interface,
                           const struct usb_device_id *id) {
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
    usb_set_intfdata(interface, kb);

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
             "USB keyboard attached vid=0x%04x pid=0x%04x endpoint=0x%02x interval=%u\n",
             le16_to_cpu(udev->descriptor.idVendor),
             le16_to_cpu(udev->descriptor.idProduct),
             irq_endpoint->bEndpointAddress,
             interval);
    dev_info(&interface->dev,
             "Unbind usbhid from this keyboard before binding kb_driver if the default driver already owns it.\n");
    return 0;

err_free_urb:
    usb_free_urb(kb->irq_urb);
err_free_buffer:
    usb_free_coherent(udev, KB_REPORT_SIZE, kb->irq_buf, kb->irq_dma);
err_free_device:
    usb_set_intfdata(interface, NULL);
    usb_put_dev(kb->udev);
    kfree(kb);
    return ret;
}

static void kb_driver_disconnect(struct usb_interface *interface) {
    struct kb_device *kb = usb_get_intfdata(interface);

    usb_set_intfdata(interface, NULL);
    if (kb == NULL) {
        return;
    }

    usb_kill_urb(kb->irq_urb);
    usb_free_urb(kb->irq_urb);
    usb_free_coherent(kb->udev, KB_REPORT_SIZE, kb->irq_buf, kb->irq_dma);
    dev_info(&interface->dev, "USB keyboard disconnected\n");
    usb_put_dev(kb->udev);
    kfree(kb);
}

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

static int __init kb_driver_init(void) {
    return usb_register(&kb_driver);
}

static void __exit kb_driver_exit(void) {
    usb_deregister(&kb_driver);
}

module_init(kb_driver_init);
module_exit(kb_driver_exit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Codex reconstruction");
MODULE_DESCRIPTION("USB boot keyboard driver with interrupt report logging");

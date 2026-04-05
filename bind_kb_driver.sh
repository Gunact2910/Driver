#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
MODULE_PATH="${PROJECT_DIR}/kb_driver.ko"

if [[ "${EUID}" -ne 0 ]]; then
    echo "Run this script as root." >&2
    exit 1
fi

if [[ ! -f "${MODULE_PATH}" ]]; then
    echo "Missing module: ${MODULE_PATH}" >&2
    exit 1
fi

if [[ ! -d /sys/bus/usb/drivers/kb_driver ]]; then
    insmod "${MODULE_PATH}"
fi

find_keyboard_ifaces() {
    local iface

    for iface in /sys/bus/usb/devices/*:*; do
        [[ -f "${iface}/bInterfaceClass" ]] || continue
        [[ "$(cat "${iface}/bInterfaceClass")" == "03" ]] || continue
        [[ "$(cat "${iface}/bInterfaceSubClass")" == "01" ]] || continue
        [[ "$(cat "${iface}/bInterfaceProtocol")" == "01" ]] || continue
        printf '%s\n' "$(basename "${iface}")"
    done
}

bind_iface() {
    local iface_name="$1"
    local iface_path="/sys/bus/usb/devices/${iface_name}"
    local current_driver=""

    if [[ ! -d "${iface_path}" ]]; then
        echo "Interface not found: ${iface_name}" >&2
        return 1
    fi

    if [[ -L "${iface_path}/driver" ]]; then
        current_driver="$(basename "$(readlink "${iface_path}/driver")")"
    fi

    if [[ "${current_driver}" == "kb_driver" ]]; then
        echo "${iface_name}: already bound to kb_driver"
        return 0
    fi

    if [[ "${current_driver}" == "usbhid" ]]; then
        echo "${iface_name}" > /sys/bus/usb/drivers/usbhid/unbind
    fi

    echo "${iface_name}" > /sys/bus/usb/drivers/kb_driver/bind
    echo "${iface_name}: bound to kb_driver"
}

main() {
    local targets=()

    if [[ "$#" -gt 0 ]]; then
        targets=("$@")
    else
        mapfile -t targets < <(find_keyboard_ifaces)
    fi

    if [[ "${#targets[@]}" -eq 0 ]]; then
        echo "No USB boot keyboard interface found." >&2
        exit 1
    fi

    for iface_name in "${targets[@]}"; do
        bind_iface "${iface_name}"
    done
}

main "$@"

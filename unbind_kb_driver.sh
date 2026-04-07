#!/usr/bin/env bash

set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "Run this script as root." >&2
    exit 1
fi

find_bound_ifaces() {
    local link

    for link in /sys/bus/usb/drivers/kb_driver/*:*; do
        [[ -L "${link}" ]] || continue
        printf '%s\n' "$(basename "${link}")"
    done
}

rebind_iface() {
    local iface_name="$1"

    echo "${iface_name}" > /sys/bus/usb/drivers/kb_driver/unbind
    echo "${iface_name}" > /sys/bus/usb/drivers/usbhid/bind
    echo "${iface_name}: rebound to usbhid"
}

main() {
    local targets=()

    if [[ "$#" -gt 0 ]]; then
        targets=("$@")
    else
        mapfile -t targets < <(find_bound_ifaces)
    fi

    if [[ "${#targets[@]}" -eq 0 ]]; then
        echo "No interface is currently bound to kb_driver." >&2
        exit 1
    fi

    for iface_name in "${targets[@]}"; do
        rebind_iface "${iface_name}"
    done
}

main "$@"

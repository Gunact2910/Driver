#!/usr/bin/env bash

set -euo pipefail

found=0

for iface in /sys/bus/usb/devices/*:*; do
    [[ -f "${iface}/bInterfaceClass" ]] || continue
    [[ "$(cat "${iface}/bInterfaceClass")" == "03" ]] || continue
    [[ "$(cat "${iface}/bInterfaceSubClass")" == "01" ]] || continue
    [[ "$(cat "${iface}/bInterfaceProtocol")" == "01" ]] || continue

    found=1
    iface_name="$(basename "${iface}")"
    device_path="$(readlink -f "${iface}/..")"
    device_name="$(basename "${device_path}")"
    vendor="$(cat "${device_path}/idVendor" 2>/dev/null || echo "????")"
    product_id="$(cat "${device_path}/idProduct" 2>/dev/null || echo "????")"
    manufacturer="$(cat "${device_path}/manufacturer" 2>/dev/null || echo "Unknown")"
    product="$(cat "${device_path}/product" 2>/dev/null || echo "Unknown")"
    if [[ -L "${iface}/driver" ]]; then
        driver="$(basename "$(readlink "${iface}/driver")")"
    else
        driver="(none)"
    fi

    echo "Interface : ${iface_name}"
    echo "USB device : ${device_name}"
    echo "Vendor:Prod: ${vendor}:${product_id}"
    echo "Device    : ${manufacturer} - ${product}"
    echo "Driver    : ${driver}"
    echo
done

if [[ "${found}" -eq 0 ]]; then
    echo "No USB boot keyboard interface found."
fi

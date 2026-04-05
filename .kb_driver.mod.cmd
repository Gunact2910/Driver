savedcmd_kb_driver.mod := printf '%s\n'   driver/usb_keyboard.o | awk '!x[$$0]++ { print("./"$$0) }' > kb_driver.mod

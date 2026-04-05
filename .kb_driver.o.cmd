savedcmd_kb_driver.o := x86_64-linux-gnu-ld -m elf_x86_64 -z noexecstack --no-warn-rwx-segments   -r -o kb_driver.o @kb_driver.mod  ; /usr/src/linux-headers-6.18.12+kali-amd64/tools/objtool/objtool --hacks=jump_label --hacks=noinstr --hacks=skylake --ibt --orc --retpoline --rethunk --sls --static-call --uaccess --prefix=16  --link  --module kb_driver.o

kb_driver.o: $(wildcard /usr/src/linux-headers-6.18.12+kali-amd64/tools/objtool/objtool)

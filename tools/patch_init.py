#!/usr/bin/env python3
"""
Init SELinux Bypass Patcher for Android 8.1 / Rockchip RK3368 (Boyue Likebook)

Disassembly context in original init (ARM64):
    0x40d128:  orr     w0, wzr, #1           (set enforce mode = 1)
    0x40d12c:  bl      0x45ee2c              (selinux_set_enforce(1))
    0x40d130:  cbnz    w0, 0x40dcdc          (if error, panic: Failed to set enforce mode)
    0x40d134:  bl      0x45d0c4              (selinux_is_enforcing())
    0x40d138:  cmp     w0, #1
    0x40d13c:  b.eq    0x40d148
    0x40d140:  orr     w0, wzr, #1
    0x40d144:  bl      0x45ee2c              (selinux_set_enforce(1))
    0x40d148:  ... continue boot ...

By patching file offset 0xd130 (virtual 0x40d130):
    Replace:  cbnz w0, 0x40dcdc (0x71 0x04 0x00 0x35) or instruction at 0xd130
    With:     b    0x40d148     (0x06 0x00 0x00 0x14)

Effect:
    Completely skips the enforce check and secondary enforce call, branching straight to 0x40d148.
    Because the kernel command line specifies `androidboot.selinux=permissive`,
    SELinux remains in Permissive mode throughout the entire Android lifecycle.
"""

import sys
import os

TARGET_OFFSET = 0xd130
PATCH_BYTES = bytes.fromhex("06000014")  # b 0x40d148 in ARM64 little-endian

def patch_init(in_path, out_path):
    with open(in_path, "rb") as f:
        data = bytearray(f.read())
        
    if len(data) <= TARGET_OFFSET + 4:
        raise ValueError(f"File {in_path} is too small to be the Likebook init binary.")
        
    original = data[TARGET_OFFSET : TARGET_OFFSET + 4]
    print(f"[*] Original bytes at 0x{TARGET_OFFSET:x}: {original.hex()}")
    
    if original == PATCH_BYTES:
        print("[!] File is already patched!")
    else:
        data[TARGET_OFFSET : TARGET_OFFSET + 4] = PATCH_BYTES
        print(f"[+] Patched bytes at 0x{TARGET_OFFSET:x}: {PATCH_BYTES.hex()} (b 0x40d148)")
        
    with open(out_path, "wb") as f:
        f.write(data)
        
    print(f"[+] Successfully wrote patched init to: {out_path}")

def main():
    if len(sys.argv) < 3:
        print("Usage: patch_init.py <input_init> <output_init>")
        sys.exit(1)
    patch_init(sys.argv[1], sys.argv[2])

if __name__ == '__main__':
    main()

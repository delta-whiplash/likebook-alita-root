#!/usr/bin/env python3
"""
Rockchip RK3368 Boot Image Tool
Calculates and updates the proprietary 11-field Rockchip SHA-1 checksum
required by Rockchip U-Boot in 'id[8]' (offset 0x240) of the Android boot header.

Standard AOSP uses an 8-field SHA-1:
    kernel_data + kernel_size + ramdisk_data + ramdisk_size + second_data + second_size

Rockchip U-Boot (rk3368 / rk30board) uses an 11-field SHA-1:
    kernel_data + kernel_size + ramdisk_data + ramdisk_size + second_data + second_size
    + tags_addr + page_size + unused + name + cmdline

Without this exact Rockchip SHA-1, Rockchip U-Boot rejects the boot image as corrupted!
"""

import sys
import os
import struct
import hashlib

def get_rk_sha1(boot_path):
    with open(boot_path, 'rb') as f:
        hdr = f.read(2048)
        if len(hdr) < 2048:
            raise ValueError(f"File {boot_path} too small (< 2048 bytes)")
        
        magic, k_sz, k_addr, r_sz, r_addr, s_sz, s_addr, tags, page, un, os_ver = struct.unpack('<8sIIIIIIIIII', hdr[:48])
        if magic != b'ANDROID!':
            raise ValueError(f"Not an Android boot image: magic={magic}")
            
        stored_sha = hdr[576:596]
        
        f.seek(page)
        k_data = f.read(k_sz)
        
        r_off = ((page + k_sz + page - 1) // page) * page
        f.seek(r_off)
        r_data = f.read(r_sz)
        
        s_off = ((r_off + r_sz + page - 1) // page) * page
        f.seek(s_off)
        s_data = f.read(s_sz)
        
        # 11-field Rockchip U-Boot SHA-1
        h = hashlib.sha1()
        h.update(k_data)
        h.update(hdr[8:12])   # k_sz
        h.update(r_data)
        h.update(hdr[16:20])  # r_sz
        h.update(s_data)
        h.update(hdr[24:28])  # s_sz
        h.update(hdr[32:36])  # tags_addr
        h.update(hdr[36:40])  # page_size
        h.update(hdr[40:48])  # unused
        h.update(hdr[48:64])  # name
        h.update(hdr[64:576]) # cmdline
        
        calc_sha = h.digest()
        
        # Standard AOSP SHA-1
        h_aosp = hashlib.sha1()
        h_aosp.update(k_data)
        h_aosp.update(hdr[8:12])
        h_aosp.update(r_data)
        h_aosp.update(hdr[16:20])
        h_aosp.update(s_data)
        h_aosp.update(hdr[24:28])
        aosp_sha = h_aosp.digest()
        
        return {
            "kernel_size": k_sz,
            "ramdisk_size": r_sz,
            "second_size": s_sz,
            "page_size": page,
            "stored_sha": stored_sha.hex(),
            "rockchip_sha": calc_sha.hex(),
            "aosp_sha": aosp_sha.hex(),
            "is_rk_valid": stored_sha == calc_sha,
            "is_aosp_valid": stored_sha == aosp_sha
        }

def patch_rk_sha1(in_path, out_path):
    with open(in_path, 'rb') as f:
        data = bytearray(f.read())
        
    hdr = data[:2048]
    magic, k_sz, k_addr, r_sz, r_addr, s_sz, s_addr, tags, page, un, os_ver = struct.unpack('<8sIIIIIIIIII', hdr[:48])
    if magic != b'ANDROID!':
        raise ValueError(f"Not an Android boot image: magic={magic}")
        
    k_data = data[page : page + k_sz]
    r_off = ((page + k_sz + page - 1) // page) * page
    r_data = data[r_off : r_off + r_sz]
    s_off = ((r_off + r_sz + page - 1) // page) * page
    s_data = data[s_off : s_off + s_sz]
    
    h = hashlib.sha1()
    h.update(k_data)
    h.update(hdr[8:12])
    h.update(r_data)
    h.update(hdr[16:20])
    h.update(s_data)
    h.update(hdr[24:28])
    h.update(hdr[32:36])
    h.update(hdr[36:40])
    h.update(hdr[40:48])
    h.update(hdr[48:64])
    h.update(hdr[64:576])
    
    calc_sha = h.digest()
    
    # Write to offset 576 (0x240) in header, clear remainder of id[8]
    data[576:596] = calc_sha
    data[596:608] = b'\x00' * 12
    
    with open(out_path, 'wb') as f:
        f.write(data)
        
    print(f"[+] Successfully wrote {out_path} with Rockchip SHA-1: {calc_sha.hex()}")

def main():
    if len(sys.argv) < 3:
        print("Usage: rk_boot_tool.py check <image.img> | patch <in.img> <out.img>")
        sys.exit(1)
        
    cmd = sys.argv[1]
    if cmd == "check":
        res = get_rk_sha1(sys.argv[2])
        print(f"File: {sys.argv[2]}")
        print(f"  Kernel: {res['kernel_size']} bytes | Ramdisk: {res['ramdisk_size']} bytes | Second: {res['second_size']} bytes")
        print(f"  Stored SHA:   {res['stored_sha']}")
        print(f"  Rockchip SHA: {res['rockchip_sha']} (Valid? {res['is_rk_valid']})")
        print(f"  AOSP SHA:     {res['aosp_sha']} (Valid? {res['is_aosp_valid']})")
    elif cmd == "patch":
        if len(sys.argv) < 4:
            print("Usage: rk_boot_tool.py patch <in.img> <out.img>")
            sys.exit(1)
        patch_rk_sha1(sys.argv[2], sys.argv[3])
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

if __name__ == '__main__':
    main()

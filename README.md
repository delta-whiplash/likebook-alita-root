# Boyue Likebook Alita (K103) - Root & SELinux Permissive Research

[![Platform: Rockchip RK3368](https://img.shields.io/badge/SoC-Rockchip%20RK3368-blue.svg)](https://en.wikipedia.org/wiki/Rockchip)
[![Android: 8.1.0](https://img.shields.io/badge/Android-8.1.0%20(Oreo)-green.svg)](https://source.android.com)
[![Kernel: Linux 4.4.103](https://img.shields.io/badge/Kernel-Linux%204.4.103%20aarch64-orange.svg)](https://kernel.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A complete, battle-tested research repository and guide for achieving **permanent root access** and **SELinux Permissive mode** on the **Boyue Likebook Alita (K103)** e-reader without wiping user data (`userdata` partition preserved) and maintaining 100% reading checkpoints and handwritten notes.

---

## 🌟 Highlights

* **Zero Userdata Wipe**: Never runs `fastboot oem unlock` (which forces an eMMC factory reset on Boyue e-readers).
* **Full Data Preservation**: Keeps all 1,184+ library books, bookmarks, highlights (`book_.db`), and handwritten notes (`/sdcard/notes/`) intact.
* **SELinux Permissive**: Reverse-engineered and cleanly bypassed inside the Android 64-bit `init` binary (`0xd130: b 0x40d148`) without kernel panics or `PLOG(FATAL)` restorecon crashes.
* **Freestanding Static `su` Binary**: Pure freestanding ARM64 `su` binary in C (`svc #0` syscalls, 2.6 KB, 0 libc dependencies) installed with SetUID permissions (`04755`) in `rootfs`.
* **Proprietary Rockchip SHA-1 Signing**: Includes Python tooling to calculate the proprietary 11-field checksum required by Rockchip U-Boot in the Android boot header (`id[8]`).
* **Instant Boot**: Boots into functional Android 8.1 in ~16–25 seconds.

---

## 📂 Repository Contents

```
├── README.md                      # Project overview and summary
├── QUICK_GUIDE.md                 # Practical, step-by-step rooting instructions
├── LICENSE                        # MIT License
├── docs/
│   ├── TECHNICAL_DEEP_DIVE.md     # In-depth architectural analysis & disassembly breakdown
│   └── FAILED_ATTEMPTS_AND_LESSONS_LEARNED.md # Complete matrix of tested methods, crashes & technical reasons
├── patches/
│   └── init_selinux.patch         # ARM64 disassembly diff of the init SELinux bypass
└── tools/
    ├── rk_boot_tool.py            # Rockchip 11-field boot header SHA-1 signer and validator
    ├── patch_init.py              # Automated binary patcher for the Likebook /init binary
    ├── su.c                       # Standalone freestanding ARM64 su implementation
    ├── build_su.sh                # Clang build script for standalone su
    └── su                         # Precompiled stripped aarch64 su binary (2.6 KB)
```

---

## 🚀 Quick Start

If you are looking for a step-by-step guide to root your device, refer directly to **[QUICK_GUIDE.md](QUICK_GUIDE.md)**.

### Summary of Commands:
```bash
# 1. Boot to Rockchip Loader mode (VID:PID 2207:330a)
adb reboot bootloader && fastboot reboot-bootloader

# 2. Dump stock boot image
rkdeveloptool rl 139264 65536 boot_stock.img

# 3. Patch init and insert su using the provided scripts
# (See QUICK_GUIDE.md for detailed steps)

# 4. Sign with Rockchip 11-field SHA-1
python3 tools/rk_boot_tool.py patch new_boot.img boot_rooted_signed.img

# 5. Flash to sector 139264 and reboot
rkdeveloptool wl 139264 boot_rooted_signed.img
rkdeveloptool rd
```

---

## 🔬 Hardware Specifications

| Component | Specification |
| :--- | :--- |
| **Model** | Boyue Likebook Alita (K103) |
| **SoC** | Rockchip RK3368 (8× Cortex-A53 @ 1.5 GHz) |
| **RAM** | 4 GB LPDDR3 |
| **Storage** | 32 GB eMMC 5.1 |
| **Display** | 10.3" E-Ink Mobius (1404 × 1872, 300 PPI, Wacom EMR Stylus) |
| **PMIC / E-Ink Driver** | TPS65185 PMIC, Rockchip EPDC controller |
| **OS Version** | Android 8.1.0 (`BYRead-V3.1.1-2021081712`) |
| **Kernel** | 4.4.103 (`SMP PREEMPT aarch64`) |

---

## 📖 Documentation & Research Notes

* **[QUICK_GUIDE.md](QUICK_GUIDE.md)**: Practical, step-by-step instructions to root your Likebook Alita without wiping data.
* **[docs/FAILED_ATTEMPTS_AND_LESSONS_LEARNED.md](docs/FAILED_ATTEMPTS_AND_LESSONS_LEARNED.md)**: Full matrix of failed attempts ("If you do X -> Y happens -> Why"), covering standard Magisk, OEM unlock wipe traps, SELinux kernel panics, and filesystem restrictions.
* **[docs/TECHNICAL_DEEP_DIVE.md](docs/TECHNICAL_DEEP_DIVE.md)**: Complete reverse-engineering breakdown, Ghidra/objdump disassemblies of `/init` and `adbd`, and the proprietary Rockchip SHA-1 checksum algorithm.

---

## 🤖 Acknowledgements & AI Heavy Lifting

The entirety of the reverse engineering, static ELF disassembly, ARM64 assembly patching, Rockchip U-Boot SHA-1 signature reconstruction, freestanding C implementation, and live hardware debugging was assisted and automated via intensive AI heavy lifting by:

* **AI Model**: **Gemini 3.8 Flash** (Thinking: High)
* **Environment**: **Google Antigravity for Linux** on **CachyOS**
* **Tooling & MCP**: **MCP REA** (*Reverse Engineering Anything*) with native aarch64 binary analysis, disassembly, and debugging toolchains.

---

## 🛡️ License

This project is licensed under the [MIT License](LICENSE).

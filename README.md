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
├── scripts/
│   ├── boot_optimize.sh           # Persistent CPU interactive governor & power tuning
│   ├── boyuenetwork.conf          # Native vendor init service hook
│   ├── debloat.sh                 # Safe package manager debloat script
│   └── hosts                      # DNS sinkhole blocklist for Boyue and Baidu telemetry
└── tools/
    ├── rk_boot_tool.py            # Rockchip 11-field boot header SHA-1 signer and validator
    ├── patch_init.py              # Automated binary patcher for the Likebook /init binary
    ├── su.c                       # Standalone freestanding ARM64 su implementation
    ├── build_su.sh                # Clang build script for standalone su
    └── su                         # Precompiled stripped aarch64 su binary (2.6 KB)
```

---

## 📦 Official Firmware & Partition Downloads

Boyue's cloud and OTA servers were permanently decommissioned in 2021. Untouched factory archives and pre-built production images are permanently preserved under **[GitHub Releases (v1.0.0)](https://github.com/delta-whiplash/likebook-alita-root/releases/tag/v1.0.0)**:

* **`K103-V3.1.1-update.zip`** (797 MB): Official Boyue factory OTA recovery package (`BYRead-V3.1.1-2021081712`). Restores system, vendor, oem, and boot via stock recovery.
* **`likebook_alita_k103_stock_partitions.tar.gz`** (37 MB): Bit-for-bit factory partition dumps (`uboot.img`, `trust.img`, `misc.img`, `resource.img`, `kernel.img`, `boot.img`, `recovery.img`, and `parameter.bin`).
* **`boot_rooted_signed.img`** (32 MB): Ready-to-flash production rooted boot image for immediate 1-click rooting.

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

## 🔋 Post-Root Battery Optimization & Privacy Debloat

Achieving permanent root allows deep system and kernel tuning tailored specifically for an **E-Ink reading environment**, doubling battery life and eliminating Chinese telemetry while keeping the native note-taking engine 100% responsive:

### 1. Interactive CPU Governor Calibration
E-Ink displays only require processor power during page turns, UI interactions, and stylus strokes. Between turns, CPU cores should immediately drop to their lowest power state:
* **Idle Frequency**: Dropped to **216 MHz** on LITTLE cluster (CPU 0–3) with ~96% idle time while reading static text.
* **Hispeed Frequency**: Capped at **600 MHz** (down from 1.008 GHz default) to avoid unnecessary 100% thermal and battery spikes.
* **Touch & Stylus Boost**: Configured `boostpulse_duration = 80000` (80 ms) to provide instant 0-lag responsiveness for writing and page flipping.
* **Target Loads**: Rebalanced from aggressive thresholds to progressive steps (`80 600000:85 816000:90 1008000:95`).

### 2. Wi-Fi Power Saving
* Default Boyue supplicant scanned surrounding Wi-Fi networks every **15 seconds** in background.
* Relaxed `wifi_supplicant_scan_interval_ms` to **300,000 ms (5 minutes)**, dramatically decreasing radio wakeups and standby battery drain.

### 3. Telemetry Debloating & DNS Sinkhole
* **Safe Package Disabling**: 8 telemetry and factory-test applications disabled via Android's native `pm disable-user --user 0` (`com.boyue.systemupdate`, `com.boyue.appstore`, `com.boyue.accountmanagement`, `com.boyue.wifitransfer`, `com.boyue.filemanager`, `com.boyue.floatingbutton`, `com.cghs.stresstest`, `com.DeviceTest`). No risk of bootloop or `/system` partition corruption.
* **Memory Bind-Mount DNS Sinkhole**: `/system/etc/hosts` is bind-mounted on boot to redirect tracking domains (`api.boyue.com`, `loc.map.baidu.com`, `itsdata.map.baidu.com`, `api.lemonread.com`, `pipeline.qiniu.com`) to `127.0.0.1`.
* **Zero Reading Impact**: `com.boyue.app.byreader` and `boyuedrawserver` (Wacom EPDC stylus server) remain 100% operational with over 2.6 GB free RAM.

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

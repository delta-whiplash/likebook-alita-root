# Technical Deep Dive: Permanent Root & SELinux Bypass on Rockchip RK3368 (Boyue Likebook Alita)

## 1. Device Architecture & Hardware Context

* **Device**: Boyue Likebook Alita (Model K103)
* **SoC**: Rockchip RK3368 (Octa-core ARM Cortex-A53 @ 1.5 GHz, 64-bit)
* **Operating System**: Android 8.1.0 (Oreo), Build `BYRead-V3.1.1-2021081712` (Security Patch: 2019-01-05)
* **Kernel**: Linux 4.4.103 (`SMP PREEMPT aarch64`)
* **Storage**: 32 GB eMMC 5.1 (`/dev/block/mmcblk1`), GPT partition layout
* **Display**: 10.3" E-Ink Mobius (1404 × 1872, TPS65185 PMIC, EPDC driver)

---

## 2. Why Conventional Rooting Methods Fail

### 2.1 The `fastboot oem unlock` Data-Wipe Trap
On consumer Android devices, unlocking the bootloader via `fastboot oem unlock` is standard. However, on Boyue/Rockchip e-readers:
1. `fastboot flash` and `fastboot oem` commands are locked by default (`remote: 'device is locked'`).
2. Running `fastboot oem unlock` on Likebook devices initiates an irreversible hardware factory reset, erasing all reading databases, highlights, and custom handwritten notes stored in `/data` and `/sdcard/notes`.

### 2.2 Rockchip U-Boot Proprietary SHA-1 Verification
When modifying the Android `boot.img`, standard tools (including standard Android `mkbootimg` and Magisk v25–v27 `magiskboot`) compute the standard AOSP 8-field SHA-1 hash over:
```
kernel_data + kernel_size + ramdisk_data + ramdisk_size + second_data + second_size
```
Rockchip's proprietary U-Boot (`rk30board` / `rk3368`) computes an **11-field SHA-1 hash**:
```
kernel_data + kernel_size + ramdisk_data + ramdisk_size + second_data + second_size
+ tags_addr + page_size + unused + name + cmdline
```
If the boot header's `id[8]` (offset `0x240`) does not match this exact 11-field digest, Rockchip U-Boot declares the boot partition corrupted and refuses to load it, falling back to Recovery mode.

### 2.3 Magisk `magiskinit` Panic
Magisk replaces the rootfs `/init` binary with `magiskinit`. On the RK3368 with Android 8.1 64-bit kernel and 32/64-bit hybrid userspace, `magiskinit` fails to bind-mount the rootfs tmpfs during early-init before Zygote starts, causing the boot sequence to hang at the boot logo.

### 2.4 Filesystem Mount Restrictions
* `/data` is mounted with `nosuid,nodev,noatime` in `init.rockchip.rc`. Any binary placed in `/data/local/tmp` with `chmod 4755` fails with `EPERM` when executed by an unprivileged user.
* `/system` is mounted as read-only backed by dm-verity (`/dev/block/dm-0`). Writing directly to `/system/bin` or `/system/xbin` is blocked at the block layer unless verity is reconstructed.

---

## 3. The Reverse-Engineering Breakthrough

### 3.1 Kernel Command Line State
Dumping `/proc/cmdline` revealed an important quirk in Boyue's bootloader configuration:
```text
androidboot.selinux=permissive androidboot.veritymode=enforcing androidboot.hardware=rk30board
```
The Linux kernel was already booting with `androidboot.selinux=permissive`! However, once userspace `init` started, SELinux was transitioned to `Enforcing` (`getenforce` returned `Enforcing`).

### 3.2 Reverse Engineering `/init` (ARM64 ELF)
Disassembling the Android 8.1 `/init` binary revealed the exact function forcing enforcement:

```armasm
; Virtual Address: 0x40d128 | File Offset: 0xd128
0x40d128:  orr     w0, wzr, #1           ; w0 = 1 (enforce)
0x40d12c:  bl      0x45ee2c              ; selinux_set_enforce(1)
0x40d130:  cbnz    w0, 0x40dcdc          ; If non-zero, panic: "Failed to set enforce mode"
0x40d134:  bl      0x45d0c4              ; selinux_is_enforcing()
0x40d138:  cmp     w0, #1
0x40d13c:  b.eq    0x40d148
0x40d140:  orr     w0, wzr, #1
0x40d144:  bl      0x45ee2c              ; selinux_set_enforce(1)
0x40d148:  ... continue initialization ...
```

#### Why Previous SELinux Patches Failed:
1. **Patching `selinux_initialize(0)`**: Completely skipped loading the SELinux policy file. Later during initialization, `selinux_android_restorecon("/init")` returned `-1` (policy not loaded), triggering a fatal `PLOG(FATAL)` kernel panic.
2. **Forcing `selinux_set_enforce(0)`**: Trying to write `0` into `/sys/fs/selinux/enforce` failed with `-EINVAL`/`-EPERM` at that stage of boot, causing `selinux_set_enforce` to return `-1`, which triggered the fatal branch `cbnz w0, 0x40dcdc`.

#### The Working Solution:
By patching file offset `0xd130` with `0x14000006` (`b 0x40d148`), the execution completely skips the enforce write and checks, jumping directly to `0x40d148`. 
Because the kernel started with `androidboot.selinux=permissive`, SELinux remains **permanently in Permissive mode** throughout the entire runtime without any panics.

---

## 4. Universal Root Execution via Rootfs SetUID

With SELinux in Permissive mode:
1. Root filesystem `/` (`rootfs`) is a RAM disk mounted **without** `nosuid` (`rw,seclabel`).
2. Directories `/sbin` and `/xbin` live directly in `rootfs`.
3. The system-wide `PATH` exported in `/init.rockchip.rc` is:
   ```text
   export PATH /sbin:/vendor/bin:/system/sbin:/system/bin:/system/xbin
   ```
   `/sbin` is the **first entry** searched across the entire system.

### Freestanding ARM64 `su` Binary
Rather than running an unstable network daemon or background listener, we compiled a standalone, freestanding ARM64 `su` binary in C with direct Linux syscalls (`svc #0`):
* `setresgid(0, 0, 0)`
* `setgroups(0, NULL)`
* `setresuid(0, 0, 0)`
* `execve("/system/bin/sh", argv, envp)`

Because the binary is statically linked with zero libc dependencies and weighs only 2.6 KB, it executes in under 2 milliseconds and is completely self-contained. 
Placed at `/sbin/su` with mode `04755` (`rwsr-xr-x`, owner `root:root`), any process (shell or third-party Android application) calling `su` immediately gains full UID 0 privileges.

---

## 5. Native ADB Root (`adbd`)

In Android 8.1, `adbd` uses `minijail` to drop privileges to `AID_SHELL` (UID 2000). The privilege drop is governed by `adbd_main`:
```cpp
if (ro.boot.verifiedbootstate == "orange" && ro.debuggable == 1 && service.adb.root == 1) {
    // Keep root privileges (AID_ROOT, uid=0, gid=0)
} else {
    minijail_change_uid(2000);
    minijail_change_gid(2000);
    minijail_enter();
}
```
Setting `service.adb.root 1`, `ro.debuggable 1`, and `ro.boot.verifiedbootstate orange` at boot allows `adbd` to run natively as `root` (`context=u:r:su:s0`), providing direct root access whenever `adb shell` is connected.

---

## 6. Flash Strategy & Bootloader Communication

Communication modes and USB VID/PID:
* **Android ADB**: `2207:0011`
* **Android Recovery**: `2207:0001`
* **Rockchip Fastboot**: `2207:0006`
* **Rockchip MaskROM / Loader**: `2207:330a`

### Direct Flashing via Rockchip Loader:
1. `adb reboot bootloader` enters Fastboot (`2207:0006`).
2. `fastboot reboot-bootloader` transitions into Rockchip Miniloader (`2207:330a`).
3. In Loader mode, `rkdeveloptool` can read and write raw sectors without triggering any userdata wipe:
   ```bash
   rkdeveloptool wl 139264 boot_signed.img
   rkdeveloptool rd
   ```
4. Sector `139,264` is the exact start of the `boot` partition (size: `33,554,432` bytes = 65,536 sectors of 512 bytes).

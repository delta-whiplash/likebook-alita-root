# Matrix of Failed Attempts, Traps & Lessons Learned

This document provides a comprehensive catalog of **every dead end, failed attempt, and technical trap** encountered while researching permanent root access on the **Boyue Likebook Alita (K103 / RK3368)**.

Its goal is to prevent others from wasting dozens of hours reproducing the same errors by providing concrete cause-and-effect explanations:
> **"If you do X ➔ Y happens ➔ Here is why under the hood."**

---

## Quick Reference: Comparative Matrix

| Action Tested | Observed Result | Technical Root Cause Under the Hood |
| :--- | :--- | :--- |
| **`fastboot oem unlock`** | ❌ Complete wipe of `userdata` or `device is locked` | Built-in routine in Boyue's bootloader that forces a hardware factory erase on eMMC when lock state changes. |
| **Standard Magisk (v25 to v30)** | ❌ Black screen / Bootloop / U-Boot rejection | 1. Standard AOSP SHA-1 (8 fields) rejected by Rockchip U-Boot (requires 11 fields).<br>2. `magiskinit` crashes during rootfs pivot on RK3368 hybrid 32/64-bit userspace. |
| **Patching `default.prop` (4 lines)** | ❌ Bootloop / Drop to Recovery | Loss of the `default.prop -> system/etc/prop.default` symlink, dropping `ro.zygote=zygote64_32` ➔ Zygote watchdog panic. |
| **Ramdisk repack with `find . \| cpio`** | ❌ Boot failure / `init` crash | Standard Linux `cpio` prepends `./` to paths and alters symlink modes (0777 instead of 0750) ➔ Rejected by Android `init`. |
| **SELinux: Bypassing `selinux_initialize(0)`** | ❌ Kernel crash / Drop to Recovery | Skips policy loading. Subsequent `selinux_android_restorecon("/init")` returns `-1` ➔ Triggers fatal `PLOG(FATAL)` panic. |
| **SELinux: Forcing `selinux_set_enforce(0)`** | ❌ Kernel crash / Drop to Recovery | Writing `0` to `/sys/fs/selinux/enforce` fails with `-EINVAL`/`-EPERM` at early boot ➔ Triggers `cbnz w0, 0x40dcdc` ("Failed to set enforce mode"). |
| **SetUID `su` binary in `/data/local/tmp`** | ❌ `EPERM` / Refusal to elevate | `/data` partition is mounted with the **`nosuid`** flag in `init.rockchip.rc`. The Linux kernel ignores the SUID bit. |
| **Direct writes to `/system`** | ❌ `Read-only file system` | `/system` partition is backed by block-level **dm-verity** (`/dev/block/dm-0`). |
| **1-Click Root APKs (KingRoot, etc.)** | ❌ Failure / App crash | Exploits rely on obsolete Linux 3.x vulnerabilities patched in Kernel 4.4.103 and Android 8.1. |
| **Setting `ro.boot.verifiedbootstate` to `orange`** | ⚠️ "Internal problem with your device" dialog on boot | Android 8.1 Treble VINTF check. Boyue's kernel was built without `CONFIG_IKCONFIG_PROC=y`, triggering `Missing config CONFIG_ANDROID`. |
| **The Golden Path (Our Working Solution)** | ✅ **Persistent Root, SELinux Permissive, 0 data loss, 16s boot** | **Single ARM64 branch patch `0x14000006` (`b 0x40d148`) in `init`, freestanding static `su` in `/sbin` (rootfs non-nosuid), Rockchip 11-field SHA-1 header signature.** |

---

## 1. The Bootloader Unlock Trap: `fastboot oem unlock`

### What Was Tested
Attempting standard fastboot OEM unlocking:
```bash
adb reboot bootloader
fastboot oem unlock
# or fastboot flashing unlock
```

### What Happened
* On standard fastboot, the command is rejected with `remote: 'device is locked'`.
* If forced through proprietary unlock commands, the bootloader automatically issues a low-level format command to sector `7,955,456` (`userdata`).

### Why Under the Hood
On Boyue e-readers, user partitions are unencrypted, but the proprietary bootloader includes a security routine: altering the OEM lock state automatically triggers an erase of the `userdata` partition.
**Golden Rule:** **NEVER** run `oem unlock`. Use **Rockchip Miniloader mode** (`2207:330a`) instead, which allows raw sector read/write without modifying OEM lock state.

---

## 2. The Standard Magisk Failure (v25, v26, v27, v30)

### What Was Tested
Patching `boot.img` using the official Magisk application or the standalone `magiskboot patch` utility.

### What Happened
* The device refuses to boot, bootloops on the Likebook splash screen, or immediately drops into Android Recovery.

### Why Under the Hood
Two distinct technical obstacles cause this:

#### Cause A: Rockchip U-Boot 11-Field SHA-1 Signature
* Standard AOSP `boot.img` computes an 8-field SHA-1 digest:
  $$\text{SHA-1}(kernel + kernel\_sz + ramdisk + ramdisk\_sz + second + second\_sz)$$
* Rockchip U-Boot (`rk3368` / `rk30board`) computes an **11-field SHA-1 digest**:
  $$\text{SHA-1}(kernel + k\_sz + ramdisk + r\_sz + second + s\_sz + tags\_addr + page\_sz + unused + name + cmdline)$$
* If offset `0x240` (`id[8]`) does not match this 11-field digest, Rockchip U-Boot treats the boot image as corrupt and boots the `recovery` partition instead.

#### Cause B: `magiskinit` Early-Boot Panic
Magisk replaces `/init` with `magiskinit`. On the RK3368 architecture running an aarch64 64-bit kernel with a 32/64-bit hybrid userspace on Android 8.1, `magiskinit` fails to properly establish the rootfs tmpfs pivot before Zygote starts, causing the Android initialization watchdog to panic.

---

## 3. SELinux Traps Inside `/init`

The Likebook kernel starts natively with `androidboot.selinux=permissive` in its command line (`/proc/cmdline`). However, during early userspace initialization, `/init` locks SELinux into `Enforcing` mode.

Here is the disassembled code of the enforcing routine in `/init` (offset `0xd128`):
```armasm
0x40d128:  orr     w0, wzr, #1           ; w0 = 1 (enforcing mode)
0x40d12c:  bl      0x45ee2c              ; call selinux_set_enforce(1)
0x40d130:  cbnz    w0, 0x40dcdc          ; IF failure (!= 0) -> FATAL panic
0x40d134:  bl      0x45d0c4              ; check selinux_is_enforcing()
0x40d138:  cmp     w0, #1
0x40d13c:  b.eq    0x40d148              ; if already enforcing, jump forward
0x40d140:  orr     w0, wzr, #1
0x40d144:  bl      0x45ee2c              ; 2nd attempt selinux_set_enforce(1)
0x40d148:  ... continue initialization ...
```

### Attempt 1: Bypassing `selinux_initialize(0)`
* **Action:** NOP out the call to `selinux_initialize` to disable SELinux from the very start.
* **Result:** Immediate drop to Recovery.
* **Why:** `selinux_initialize` not only sets the enforcement mode but also loads the SELinux policy (`/sepolicy`). Shortly after, `init` calls `selinux_android_restorecon("/init")`. Because no policy is loaded, this returns `-1`, triggering `PLOG(FATAL) << "restorecon failed"`.

### Attempt 2: Forcing `selinux_set_enforce(0)`
* **Action:** Change the argument `w0` at `0x40d128` to `0` instead of `1`.
* **Result:** Immediate drop to Recovery.
* **Why:** `selinux_set_enforce(0)` attempts to write `"0"` to `/sys/fs/selinux/enforce`. At this stage of boot in Android 8.1, the kernel SELinux pseudo-filesystem rejects this write with `-EINVAL`/`-EPERM`. The function returns `-1`. The check at `0x40d130` (`cbnz w0, 0x40dcdc`) detects `w0 != 0` and jumps straight into `PLOG(FATAL) << "Failed to set enforce mode"`.

### ✅ The Winning Solution: The Unconditional Branch
* **Action:** Replace the instruction at file offset `0xd130` (`cbnz w0, 0x40dcdc`) with:
  ```armasm
  b 0x40d148    ; ARM64 opcode: 0x14000006 (little-endian: 06 00 00 14)
  ```
* **Result:** Total success. The execution jumps directly past both the error check and the second enforcing call. The kernel remains in its default `androidboot.selinux=permissive` state, policy loading succeeds, and zero panics occur.

---

## 4. Ramdisk and Filesystem Traps

### Attempt: Replacing `default.prop` with a Custom 4-Line File
* **Action:** Creating a new `default.prop` containing only `ro.secure=0` and `ro.debuggable=1`.
* **Result:** Complete bootloop, Zygote never spawns.
* **Why:** In Android 8.1, `default.prop` is a **symlink** to `system/etc/prop.default`. Replacing it with a short file drops critical system properties, notably `ro.zygote=zygote64_32`. Without this property, `init` does not know which Zygote binary to start.
* **Rule:** Always preserve the `default.prop -> system/etc/prop.default` symlink intact.

### Attempt: Repacking Ramdisk with Host Linux `find . | cpio`
* **Action:** `find . | cpio -o -H newc | gzip > ramdisk.cpio`.
* **Result:** Boot failure.
* **Why:** The standard host `find` command prepends `./` to file paths (`./init`, `./sbin`). Furthermore, standard cpio resets symlink permissions to `0777`. The Android `init` parser explicitly rejects relative `./` paths for early binary execution.
* **Rule:** Exclusively use `magiskboot cpio ramdisk.cpio "<command>"` for in-place modifications to preserve exact Android CPIO headers and octal permissions.

---

## 5. SetUID and Binary Execution Traps

### Attempt: Installing SetUID `su` in `/data/local/tmp`
* **Action:** `cp su /data/local/tmp/su && chmod 4755 /data/local/tmp/su`.
* **Result:** When run by an unprivileged user, the binary returns `EPERM` or remains with `uid=2000`.
* **Why:** In `init.rockchip.rc`, `/data` is mounted with:
  ```text
  mount dummy dummy /data remount nosuid nodev noatime
  ```
  The Linux kernel's `nosuid` flag neutralizes the SetUID bit for all executables located on that mount point.

### ✅ The Winning Solution: Installation in `/sbin` (Rootfs)
* **Why `/sbin` works:**
  1. `/sbin` resides directly in `rootfs` (RAMDisk tmpfs mounted on `/`).
  2. The rootfs mount options are: `rootfs on / type rootfs (rw,seclabel)` ➔ **NO `nosuid` flag**!
  3. The system-wide `$PATH` exported in `/init.rockchip.rc` begins with `/sbin`:
     ```text
     export PATH /sbin:/vendor/bin:/system/sbin:/system/bin:/system/xbin
     ```
  4. Injecting a freestanding ARM64 `su` binary in mode `04755` into `/sbin/su` allows any process to invoke `su` and immediately gain `uid=0` without relying on background sockets or daemons.

---

## 6. The Treble VINTF Warning Dialog

### What Happened
After booting an image where `ro.boot.verifiedbootstate` was forced to `orange` via `resetprop`, a system alert appeared on screen:
> *"There's an internal problem with your device. Contact your manufacturer for details."*

### Why Under the Hood
In Android 8.1 AOSP (`ActivityManagerService.java`):
```java
if (!Build.isBuildConsistent()) {
    Slog.e(TAG, "Build fingerprint is not consistent, warning user");
    showInternalErrorDialog();
}
```
In `Build.java`, `isBuildConsistent()` calls the Treble validator:
```java
int result = VintfObject.verify(packageInfo);
```
In the logcat:
```text
VintfObject.verify() returns 1: Runtime info and framework compatibility matrix are incompatible: Missing config CONFIG_ANDROID
```
* **Explanation:** `/system/compatibility_matrix.xml` requires kernel options to be exposed in `/proc/config.gz`. Boyue's kernel 4.4 was compiled without `CONFIG_IKCONFIG_PROC=y`. Because the file is missing, the validator flags the kernel as incompatible and triggers the warning dialog.
* **Impact:** Purely visual. The reading application, handwritten notes, and system run with 100% stability.
* **Solution:** Keep `ro.boot.verifiedbootstate` on `green`, or auto-dismiss the dialog via a background watcher on boot (`input tap 1137 1045`).

---

### 10. Flashing via `dd` in Userspace vs Low-Level Sector Offsets

* **What we tried:** Attempted to write the modified `boot.img` directly from within Android using `dd if=... of=/dev/block/platform/ff0f0000.dwmmc/by-name/boot`.
* **What happened:** Device dropped into Recovery mode upon reboot.
* **Why it failed:** 
  1. The Android userspace symlink `/dev/block/platform/.../by-name/boot` pointed to `/dev/block/mmcblk1p7`, which began at sector **147456** in the GPT table.
  2. However, the Rockchip Miniloader and U-Boot parameter table maps `boot` starting at sector **139264** (`0x22000`).
  3. Writing to 147456 shifted the written image by 8,192 sectors (4 MB) into the adjacent partition space, corrupting the boundary and triggering recovery fallback.
* **Lesson Learned:** Always flash boot images from the Rockchip Miniloader (`rkdeveloptool wl 139264`) rather than raw block device nodes in userspace.

---

### 11. PMIC RK818 Protective Standby after `rkdeveloptool rd`

* **What we tried:** Sent a low-level reboot command (`rkdeveloptool rd`) to reset the device after flashing while the USB-C cable was plugged into the host PC.
* **What happened:** The device disconnected from USB and appeared completely unresponsive; short presses on the Power button had no visible effect.
* **Why it failed:** The RK3368 SoC's dedicated power management chip (Rockchip RK818 PMIC) enters a hardware protective low-power standby mode when an automated reset is executed while 5V VBUS voltage is continuously supplied over USB.
* **Solution:** Disconnect the USB cable, hold the physical Power button down continuously for 25 to 30 seconds to drain residual charge from the PMIC rail capacitors, then reconnect and power on normally (or use the hardware *Upgrade Key* in the pinhole next to the Power button).

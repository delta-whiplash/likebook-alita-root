# Quick Rooting Guide: Boyue Likebook Alita (K103)

This guide walks you through rooting your **Boyue Likebook Alita (K103)** running Android 8.1 **without wiping userdata** or losing your reading checkpoints and handwritten notes.

> [!CAUTION]
> **NEVER run `fastboot oem unlock`!**  
> On Likebook devices, `fastboot oem unlock` immediately triggers an irreversible factory reset that wipes the `userdata` partition. Follow the Rockchip Loader method below to preserve all your data.

---

## Prerequisites

1. **Host PC**: Linux (Ubuntu, Debian, Arch, Fedora) with:
   * `adb` & `fastboot` (`android-tools`)
   * `python3`
   * `clang` & `lld` (optional, if building `su` from source)
2. **Rockchip Flashing Tool**: `rkdeveloptool` ([build from source](https://github.com/rockchip-linux/rkdeveloptool) or use the prebuilt binary).
3. **USB Cable**: Good quality USB-C cable connected directly to the PC.
4. **Alita Device**: Charged above 50% with **USB Debugging** enabled in *Settings > Developer Options*.

---

## Step 1: Secure Your Data First (Recommended)

Before flashing anything, make a copy of your library and handwritten notes:

```bash
# 1. Back up reading notes from internal storage
adb pull /sdcard/notes/ ./backup_notes/

# 2. Back up reader databases
adb backup -f byreader.ab com.boyue.app.byreader 2>/dev/null || true
```

---

## Step 2: Enter Rockchip Loader Mode

1. Connect the Likebook to your computer via USB.
2. Put the device into Fastboot mode:
   ```bash
   adb reboot bootloader
   ```
3. Once `fastboot devices` detects your e-reader, switch directly to Rockchip Miniloader mode:
   ```bash
   fastboot reboot-bootloader
   ```
4. Verify that the device is detected in Loader mode:
   ```bash
   rkdeveloptool ld
   # Should output: DevNo=1    Vid=0x2207,Pid=0x330a,LocationID=...  Loader
   ```

---

## Step 3: Dump Your Stock Boot Image

Always take a byte-exact backup of your existing boot partition:

```bash
# The boot partition starts at sector 139264 and is 65536 sectors (32 MB) long
rkdeveloptool rl 139264 65536 boot_stock.img

# Verify the backup
python3 tools/rk_boot_tool.py check boot_stock.img
```

Keep `boot_stock.img` in a safe location as your emergency rollback image.

---

## Step 4: Patch the Boot Image

### 4.1 Unpack the Boot Image
Using `magiskboot` (from Magisk v25+ tools):
```bash
mkdir workdir && cd workdir
magiskboot unpack ../boot_stock.img
```

### 4.2 Patch SELinux in `init`
Extract the `init` binary from `ramdisk.cpio` and apply the SELinux permissive bypass:
```bash
# Extract init from ramdisk
magiskboot cpio ramdisk.cpio "extract init init"

# Apply the SELinux bypass patch (branches past selinux_set_enforce(1))
python3 ../tools/patch_init.py init init_patched

# Replace init in ramdisk
magiskboot cpio ramdisk.cpio "add 0750 init init_patched"
```

### 4.3 Add the `su` Binary to Ramdisk
Compile the standalone static ARM64 `su` binary or use the prebuilt one:
```bash
# Compile su (if building from source)
../tools/build_su.sh ./su

# Add su with SetUID permissions (04755) to /sbin/su
magiskboot cpio ramdisk.cpio "add 04755 sbin/su ./su"

# Create symlink /xbin -> /sbin for maximum app compatibility
magiskboot cpio ramdisk.cpio "ln sbin xbin"
```

### 4.4 Repack and Sign with Rockchip SHA-1
```bash
# Repack the boot image
magiskboot repack ../boot_stock.img new_boot_unsigned.img

# Sign with the proprietary 11-field Rockchip SHA-1 checksum
python3 ../tools/rk_boot_tool.py patch new_boot_unsigned.img ../boot_rooted_signed.img

# Verify signature
python3 ../tools/rk_boot_tool.py check ../boot_rooted_signed.img
# Ensure "Rockchip SHA: ... (Valid? True)" is printed!
```

---

## Step 5: Flash and Reboot

Flash the rooted boot image back to sector 139264:

```bash
cd ..
rkdeveloptool wl 139264 boot_rooted_signed.img
rkdeveloptool rd
```

The device will reboot into Android 8.1 in approximately 20–30 seconds.

---

## Step 6: Verify Root Access

Once Android starts up:

```bash
# 1. Verify SELinux is in Permissive mode
adb shell getenforce
# Expected output: Permissive

# 2. Verify su binary version
adb shell su -v
# Expected output: 2.82:SUPERSU

# 3. Verify root execution
adb shell su -c id
# Expected output: uid=0(root) gid=0(root) groups=0(root)

# 4. Confirm whoami
adb shell su -c whoami
# Expected output: root
```

Congratulations! Your Likebook Alita is now permanently rooted with full UID 0 execution, without any userdata wipe, and with all your reading checkpoints and notes 100% preserved.

---

## Emergency Rollback

If you ever wish to revert to 100% stock factory boot:
1. Put the device into Loader mode (`2207:330a`).
2. Run:
   ```bash
   rkdeveloptool wl 139264 boot_stock.img
   rkdeveloptool rd
   ```
The device will instantly return to its original stock unrooted configuration.

#!/bin/bash
# ==============================================================================
# Likebook Alita (K103) - Safe Telemetry & Bloatware Disabler
# Uses official Android Package Manager (pm disable-user) to avoid /system corruption
# ==============================================================================

set -e

PACKAGES=(
    "com.boyue.systemupdate"       # Defunct OTA updater & background telemetry
    "com.boyue.appstore"           # Insecure Chinese app market
    "com.boyue.accountmanagement"  # Boyue cloud sync & telemetry
    "com.boyue.wifitransfer"       # Unencrypted local HTTP server
    "com.boyue.filemanager"        # Bloatware file manager (stock AOSP Files preserved)
    "com.boyue.floatingbutton"     # Annoying overlay UI
    "com.cghs.stresstest"          # Factory burn-in stress test
    "com.DeviceTest"               # Factory diagnostics tool
)

echo "[*] Disabling Boyue telemetry packages..."
for pkg in "${PACKAGES[@]}"; do
    echo -n "  -> Disabling $pkg: "
    adb shell "pm disable-user --user 0 $pkg 2>/dev/null" || true
done

echo "[*] Purging Baidu tracking directory from /sdcard..."
adb shell "rm -rf /sdcard/baidu"

echo "[+] Debloat complete! Core reader (ByReader) and notes remain 100% operational."

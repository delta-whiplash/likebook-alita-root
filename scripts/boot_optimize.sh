#!/system/bin/sh
# ==============================================================================
# Boyue Likebook Alita (K103) - Boot Optimization & Power Tuning Script
# ==============================================================================

# 1. Sinkhole Boyue Telemetry & Baidu Tracking via hosts bind-mount
if [ -f /data/boyue/hosts ]; then
    mount -o bind /data/boyue/hosts /system/etc/hosts 2>/dev/null || true
fi

# 2. Wi-Fi Power Saving: Change scan interval from 15s to 300s (5 minutes)
settings put global wifi_supplicant_scan_interval_ms 300000 2>/dev/null || true
setprop wifi.supplicant_scan_interval 300 2>/dev/null || true

# 3. CPU Governor Tuning (Interactive: Responsive yet Battery-Efficient for E-Ink)
# Cluster 0 (LITTLE: CPU 0-3)
if [ -d /sys/devices/system/cpu/cpufreq/policy0/interactive ]; then
    echo 600000 > /sys/devices/system/cpu/cpufreq/policy0/interactive/hispeed_freq
    echo 85 > /sys/devices/system/cpu/cpufreq/policy0/interactive/go_hispeed_load
    echo '40000 816000:60000 1008000:80000' > /sys/devices/system/cpu/cpufreq/policy0/interactive/above_hispeed_delay
    echo '80 600000:85 816000:90 1008000:95' > /sys/devices/system/cpu/cpufreq/policy0/interactive/target_loads
    echo 60000 > /sys/devices/system/cpu/cpufreq/policy0/interactive/min_sample_time
    echo 30000 > /sys/devices/system/cpu/cpufreq/policy0/interactive/timer_rate
    echo 80000 > /sys/devices/system/cpu/cpufreq/policy0/interactive/boostpulse_duration
fi

# Cluster 4 (BIG: CPU 4-7)
if [ -d /sys/devices/system/cpu/cpufreq/policy4/interactive ]; then
    echo 600000 > /sys/devices/system/cpu/cpufreq/policy4/interactive/hispeed_freq
    echo 90 > /sys/devices/system/cpu/cpufreq/policy4/interactive/go_hispeed_load
    echo '40000 816000:60000 1008000:80000' > /sys/devices/system/cpu/cpufreq/policy4/interactive/above_hispeed_delay
    echo '85 816000:90 1008000:95' > /sys/devices/system/cpu/cpufreq/policy4/interactive/target_loads
    echo 60000 > /sys/devices/system/cpu/cpufreq/policy4/interactive/min_sample_time
    echo 30000 > /sys/devices/system/cpu/cpufreq/policy4/interactive/timer_rate
fi

# 4. Auto-dismiss internal warning dialog if present on boot
for i in $(seq 1 15); do
    if dumpsys window windows 2>/dev/null | grep -q "Système Android"; then
        input tap 1137 1045 2>/dev/null || input keyevent KEYCODE_ENTER 2>/dev/null
        break
    fi
    sleep 1
done

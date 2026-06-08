#!/bin/sh

echo "[stop] Stopping drone_fc..."

killall drone_fc 2>/dev/null
sleep 1

safe_pwm() {
    CHIP="$1"
    CH="$2"

    if [ -d "$CHIP/pwm$CH" ]; then
        echo 0 > "$CHIP/pwm$CH/enable" 2>/dev/null
        echo 20000000 > "$CHIP/pwm$CH/period" 2>/dev/null
        echo 1000000 > "$CHIP/pwm$CH/duty_cycle" 2>/dev/null
        echo 1 > "$CHIP/pwm$CH/enable" 2>/dev/null
    fi
}

safe_pwm /sys/class/pwm/pwmchip8 1
safe_pwm /sys/class/pwm/pwmchip8 0
safe_pwm /sys/class/pwm/pwmchip4 3
safe_pwm /sys/class/pwm/pwmchip4 0

echo "[stop] Motors set to 1000us if PWM sysfs is available."
echo "[stop] Done."

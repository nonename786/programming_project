#!/bin/sh

CONFIG_FILE="/root/drone_fc.env"
PINMUX_SCRIPT="/root/set_pinmux.sh"
DRONE_BIN="/root/drone_fc"
LOG_FILE="/root/drone_fc.log"
START_LOG="/root/drone_start.log"

echo "==================================================" >> "$START_LOG"
echo "[start] Drone fly-basic auto-start at $(date)" >> "$START_LOG"
echo "==================================================" >> "$START_LOG"

if [ ! -x "$DRONE_BIN" ]; then
    echo "[start] ERROR: $DRONE_BIN not found or not executable" >> "$START_LOG"
    exit 1
fi

if [ -f "$CONFIG_FILE" ]; then
    echo "[start] Loading config: $CONFIG_FILE" >> "$START_LOG"
    . "$CONFIG_FILE"
else
    echo "[start] WARNING: config file not found" >> "$START_LOG"
fi

echo "[start] Stop old drone_fc process if exists" >> "$START_LOG"
killall drone_fc 2>/dev/null
sleep 1

echo "[start] Waiting for system devices..." >> "$START_LOG"
sleep "${DRONE_BOOT_DELAY:-8}"

if [ -x "$PINMUX_SCRIPT" ]; then
    echo "[start] Running pinmux script..." >> "$START_LOG"
    "$PINMUX_SCRIPT" >> "$START_LOG" 2>&1
else
    echo "[start] WARNING: pinmux script not found: $PINMUX_SCRIPT" >> "$START_LOG"
fi

CMD="$DRONE_BIN --fly-basic"
CMD="$CMD --ibus-port ${DRONE_IBUS_PORT:-/dev/ttyS1}"
CMD="$CMD --bt-port ${DRONE_BT_PORT:-/dev/ttyS2}"
CMD="$CMD --bt-baud ${DRONE_BT_BAUD:-9600}"
CMD="$CMD --i2c-dev ${DRONE_I2C_DEV:-/dev/i2c-1}"
CMD="$CMD --max-pwm ${DRONE_MAX_PWM:-1550}"

if [ "$DRONE_NO_BMP" = "1" ]; then
    CMD="$CMD --no-bmp"
fi

if [ "$DRONE_NO_BATTERY" = "1" ]; then
    CMD="$CMD --no-battery"
fi

echo "[start] Final command:" >> "$START_LOG"
echo "[start] $CMD" >> "$START_LOG"

echo "==================================================" >> "$LOG_FILE"
echo "[drone_fc] Auto-started at $(date)" >> "$LOG_FILE"
echo "==================================================" >> "$LOG_FILE"

if [ "$DRONE_USE_CHRT" = "1" ]; then
    echo "[start] Running with chrt priority" >> "$START_LOG"
    chrt -f 80 $CMD >> "$LOG_FILE" 2>&1 &
else
    echo "[start] Running normally" >> "$START_LOG"
    $CMD >> "$LOG_FILE" 2>&1 &
fi

echo "[start] drone_fc pid: $!" >> "$START_LOG"
echo "[start] done" >> "$START_LOG"

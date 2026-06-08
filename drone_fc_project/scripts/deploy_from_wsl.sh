#!/usr/bin/env bash
set -euo pipefail

BOARD="${BOARD:-root@192.168.42.1}"
SSH_OPTS=(-o ConnectTimeout=8 -o ServerAliveInterval=3 -o ServerAliveCountMax=2)

echo "[1/5] Build drone_fc"
make clean
make

echo "[2/5] Prepare board and stop old program"
ssh "${SSH_OPTS[@]}" "$BOARD" '
    echo "[board] connected"
    killall drone_fc 2>/dev/null || true
    sleep 1
    rm -f /root/drone_fc
    echo "[board] old program stopped and old binary removed"
'

echo "[3/5] Copy files to $BOARD"
scp "${SSH_OPTS[@]}" drone_fc "$BOARD:/root/drone_fc"
scp "${SSH_OPTS[@]}" scripts/start_drone.sh "$BOARD:/root/start_drone.sh"
scp "${SSH_OPTS[@]}" scripts/stop_drone.sh "$BOARD:/root/stop_drone.sh"
scp "${SSH_OPTS[@]}" scripts/set_pinmux.sh "$BOARD:/root/set_pinmux.sh"
scp "${SSH_OPTS[@]}" config/drone_fc.env "$BOARD:/root/drone_fc.env"
scp "${SSH_OPTS[@]}" scripts/S99drone "$BOARD:/etc/init.d/S99drone"

echo "[4/5] Set permissions"
ssh "${SSH_OPTS[@]}" "$BOARD" '
    chmod +x /root/drone_fc
    chmod +x /root/start_drone.sh
    chmod +x /root/stop_drone.sh
    chmod +x /root/set_pinmux.sh
    chmod +x /etc/init.d/S99drone
    sync
    echo "[board] permissions set"
'

echo "[5/5] Verify deployed files"
ssh "${SSH_OPTS[@]}" "$BOARD" '
    echo "===== drone_fc ====="
    ls -lh /root/drone_fc

    echo "===== scripts ====="
    ls -lh /root/start_drone.sh /root/stop_drone.sh /root/set_pinmux.sh /etc/init.d/S99drone

    echo "===== config ====="
    cat /root/drone_fc.env
'

echo "Deploy finished."

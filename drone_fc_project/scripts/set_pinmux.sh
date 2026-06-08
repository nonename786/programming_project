#!/bin/sh

echo "======================================"
echo "[pinmux] Drone FC pinmux setup start"
echo "======================================"

echo "[pinmux] Motor PWM pins"
duo-pinmux -w GP6/PWM_9
duo-pinmux -w GP7/PWM_8
duo-pinmux -w GP8/PWM_7
duo-pinmux -w GP9/PWM_4

echo "[pinmux] IA6B iBUS receiver pin"
duo-pinmux -w GP3/UART1_RX

echo "[pinmux] MPU6050 I2C pins"
duo-pinmux -w GP4/IIC_SCL
duo-pinmux -w GP5/IIC_SDA

echo "[pinmux] HC-05 Bluetooth UART2 pins"
duo-pinmux -w GP0/UART2_TX
duo-pinmux -w GP1/UART2_RX

echo "======================================"
echo "[pinmux] Current important pin status"
echo "======================================"

duo-pinmux -r GP0
duo-pinmux -r GP1
duo-pinmux -r GP3
duo-pinmux -r GP4
duo-pinmux -r GP5
duo-pinmux -r GP6
duo-pinmux -r GP7
duo-pinmux -r GP8
duo-pinmux -r GP9

echo "======================================"
echo "[pinmux] Drone FC pinmux setup done"
echo "======================================"

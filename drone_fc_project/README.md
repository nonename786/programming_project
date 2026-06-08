# Milk-V Duo 256 无人机飞控项目(第三个无人机大作业的代码)

这是按你当前无人机硬件和阶段总结整理出来的一套 C++ 飞控工程。默认匹配：

- Milk-V Duo 256 主控
- IA6B 接收机 i-BUS：GP3 / UART1_RX
- MPU6050：GP4 / GP5 I2C，地址 0x68
- 四合一电调：GP6~GP9 四路 PWM
- 电机布局：M1 左前、M2 右前、M3 左后、M4 右后
- HC-05 蓝牙：GP0 / GP1，按你已经测试成功的串口设备名配置
- BMP180/BMP280：自动识别 0x77/0x76，用于温度/气压/高度趋势回传
- VoltageSensor：S 脚经过 10k/20k 二级分压后接 GP26/ADC，用于电池电压检测

> 安全提醒：本工程提供完整飞控软件框架，但真实稳定飞行还必须完成无桨电机编号、电机转向、螺旋桨方向、IMU 安装方向、PID 补偿方向和 PID 参数调试。第一次上电和所有测试必须拆掉螺旋桨。

## 1. 项目结构

```text
drone_fc_project/
├── Makefile
├── README.md
├── config/
│   └── drone_fc.env              # 板端运行配置，复制到 /root/drone_fc.env
├── include/
│   ├── battery.h                 # GP26 ADC 电池电压检测
│   ├── bmp_sensor.h              # BMP180/BMP280 温度气压传感器
│   ├── common.h                  # 时间、文件、环境变量等工具
│   ├── config.h                  # 引脚/PWM/PID/阈值默认参数
│   ├── esc_pwm.h                 # sysfs PWM 控制四合一电调
│   ├── mpu6050.h                 # MPU6050 驱动与互补滤波
│   ├── pid.h                     # PID 控制器
│   ├── rc_ibus.h                 # IA6B i-BUS 解析
│   └── telemetry.h               # 蓝牙/日志 CSV 回传
├── scripts/
│   ├── deploy_from_wsl.sh        # WSL 编译并上传到 Milk-V
│   ├── set_pinmux.sh             # 设置 GP6~GP9 PWM、GP3 UART、GP4/GP5 I2C
│   ├── start_drone.sh            # 板端开机启动脚本
│   ├── stop_drone.sh             # 停止飞控并写回 1000us
│   └── S99drone                  # /etc/init.d 开机自启动服务
└── src/
    ├── battery.cpp
    ├── bmp_sensor.cpp
    ├── common.cpp
    ├── esc_pwm.cpp
    ├── main.cpp
    ├── mpu6050.cpp
    ├── rc_ibus.cpp
    └── telemetry.cpp
```

## 2. 当前实现的功能

### 2.1 飞行控制主循环

`./drone_fc --fly` 进入 100Hz 主循环：

1. 读取 IA6B i-BUS 遥控器通道。
2. 读取 MPU6050 加速度和角速度。
3. 用互补滤波计算 roll / pitch / yaw。
4. CH1 映射 roll 目标角，CH2 映射 pitch 目标角，CH4 映射 yaw 目标角速度。
5. roll、pitch、yaw 三通道 PID 输出修正量。
6. 按 M1 左前、M2 右前、M3 左后、M4 右后的布局混控。
7. 通过 sysfs PWM 写四合一电调。
8. 低频读取 BMP180/BMP280 和电池电压。
9. 通过 HC-05 蓝牙串口和日志文件持续回传 CSV 数据。

### 2.2 安全逻辑

- 程序启动后默认锁定，四个电机输出 `1000us`。
- CH5 未打开时，四个电机永远 `1000us`。
- 只有遥控器有效、CH5 打开、CH3 油门最低、IMU 正常时才允许解锁。
- 遥控器失联立即锁定。
- CH5 关闭立即锁定。
- roll/pitch 超过 `45°` 立即锁定。
- 程序收到 `Ctrl+C` 或服务停止时，会写回四个电机 `1000us`。
- 电池低于 `10.8V` 标记低电提醒，低于 `10.2V` 限制最大油门，低于 `9.6V` 进入强制降落式油门上限递减。

### 2.3 遥控通道定义

| 通道 | 功能 |
|---|---|
| CH1 | Roll 横滚 |
| CH2 | Pitch 俯仰 |
| CH3 | Throttle 油门 |
| CH4 | Yaw 偏航角速度 |
| CH5 | Arm / Disarm 解锁开关 |

### 2.4 PWM 映射

| 电机 | 位置 | Milk-V 引脚 | PWM sysfs |
|---|---|---|---|
| M1 | 左前 | GP6 / PWM_9 | `/sys/class/pwm/pwmchip8` channel 1 |
| M2 | 右前 | GP7 / PWM_8 | `/sys/class/pwm/pwmchip8` channel 0 |
| M3 | 左后 | GP8 / PWM_7 | `/sys/class/pwm/pwmchip4` channel 3 |
| M4 | 右后 | GP9 / PWM_4 | `/sys/class/pwm/pwmchip4` channel 0 |

## 3. 在 WSL 中编译

进入工程目录：

```bash
cd ~/milkv-drone/drone_fc_project
```

如果你把工程放在 `~/duo-examples` 外面，先加载 Milk-V 的交叉编译环境：

```bash
cd ~/duo-examples
source envsetup.sh
cd ~/milkv-drone/drone_fc_project
```

编译：

```bash
make clean
make
```

生成：

```text
./drone_fc
```

## 4. 上传到 Milk-V 并安装开机自启动

确保 Milk-V 可以通过 USB 网络访问：

```bash
ping 192.168.42.1
```

一键编译、上传、安装：

```bash
cd ~/milkv-drone/drone_fc_project
./scripts/deploy_from_wsl.sh
```

这个脚本会把以下文件放到板子：

```text
/root/drone_fc
/root/start_drone.sh
/root/set_pinmux.sh
/root/stop_drone.sh
/root/drone_fc.env
/etc/init.d/S99drone
```

## 5. 板子上手动测试顺序

登录板子：

```bash
ssh root@192.168.42.1
```

### 5.1 设置 pinmux

```bash
/root/set_pinmux.sh
```

如有报错，先用：

```bash
duo-pinmux -r GP6
duo-pinmux -r GP7
duo-pinmux -r GP8
duo-pinmux -r GP9
duo-pinmux -r GP3
duo-pinmux -r GP4
duo-pinmux -r GP5
```

确认功能名是否和脚本一致。

### 5.2 测 MPU6050

```bash
/root/drone_fc --imu-test
```

正常表现：平放时 roll/pitch 接近 0，轻轻倾斜时角度变化。

### 5.3 测遥控器 i-BUS

```bash
/root/drone_fc --ibus-test --ibus-port /dev/ttyS1
```

如果没有 CH1~CH6 数据，修改 `/root/drone_fc.env` 中的 `DRONE_IBUS_PORT`。

### 5.4 测蓝牙回传

先确认 `/root/drone_fc.env` 里的：

```bash
DRONE_BT_PORT=/dev/ttyS4
DRONE_BT_BAUD=115200
```

改成你蓝牙测试成功的串口设备和波特率。

运行主程序但不写 PWM：

```bash
/root/drone_fc --fly --dry-run
```

手机蓝牙串口助手应能看到 CSV 数据。如果看不到，检查 `DRONE_BT_PORT`。

### 5.5 测电池电压

VoltageSensor 必须按下面方式接，不能直接把 S 接 GP26：

```text
VoltageSensor S -> 10k -> ADC节点 -> GP26
ADC节点 -> 20k -> GND
```

测试：

```bash
/root/drone_fc --battery-test
```

用万用表测电池真实电压，然后校准 `/root/drone_fc.env`：

```bash
DRONE_BATTERY_SCALE=7.5
```

### 5.6 测电调和电机，必须拆桨

```bash
/root/drone_fc --esc-test --i-understand-no-props
```

它会依次让 M1、M2、M3、M4 以 1100us 低速转动。确认：

- M1 是左前
- M2 是右前
- M3 是左后
- M4 是右后
- 电机转向和桨方向正确

## 6. 手动启动飞控

```bash
/root/start_drone.sh
```

看日志：

```bash
tail -f /root/drone_fc.log
```

程序启动后状态应该类似：

```text
DRONE_START
PWM_OK_WAIT_IMU
IMU_OK
IBUS_PORT_OK
WAIT_RC_AND_ARM
```

真正解锁流程：

1. 遥控器打开。
2. CH5 保持锁定。
3. 油门 CH3 拉到最低。
4. 插电等待 Milk-V 启动。
5. 手机蓝牙连接 HC-05，看回传状态。
6. CH5 拨到解锁。
7. 轻推油门。

## 7. 设置开机自动运行

部署脚本已经安装 `/etc/init.d/S99drone`。手动启动服务：

```bash
/etc/init.d/S99drone start
```

检查：

```bash
ps | grep drone_fc
```

重启测试：

```bash
reboot
```

重启后重新 SSH 进去：

```bash
ps | grep drone_fc
tail -f /root/drone_fc.log
```

停止：

```bash
/etc/init.d/S99drone stop
# 或
/root/stop_drone.sh
```

## 8. 第一次试飞前必须做的方向检查

无桨运行：

```bash
/root/drone_fc --fly
```

解锁后手拿机架倾斜：

- 右倾时，右侧电机应该加速，有把右侧抬起的趋势。
- 左倾时，左侧电机应该加速。
- 机头向下时，前侧电机应该加速，有把机头抬起的趋势。
- 偏航杆向右时，对角电机差速方向应符合实际转向。

如果方向反了，先不要装桨，修改 `/root/drone_fc.env` 或 `include/config.h`：

```bash
DRONE_ROLL_MIX_SIGN=-1
DRONE_PITCH_MIX_SIGN=-1
DRONE_YAW_MIX_SIGN=-1
```

每次只改一个方向，重新测试。

## 9. 关键文件位置

```text
/root/drone_fc                  飞控程序
/root/drone_fc.env              板端运行配置
/root/start_drone.sh            开机启动脚本
/root/set_pinmux.sh             引脚复用脚本
/root/stop_drone.sh             停机脚本
/etc/init.d/S99drone            开机自启动服务
/root/drone_fc.log              程序运行日志
/root/drone_fc_telemetry.csv    姿态/遥控/电池/气压/电机 CSV 数据
```

#pragma once

#include <string>
#include <vector>

namespace drone {

// =========================
// 你当前硬件接线默认值
// =========================

// 电机布局：
// M1 = 左前, M2 = 右前, M3 = 左后, M4 = 右后
// sysfs PWM 映射来自你阶段总结：
// M1: GP6 -> PWM_9 -> /sys/class/pwm/pwmchip8 channel 1
// M2: GP7 -> PWM_8 -> /sys/class/pwm/pwmchip8 channel 0
// M3: GP8 -> PWM_7 -> /sys/class/pwm/pwmchip4 channel 3
// M4: GP9 -> PWM_4 -> /sys/class/pwm/pwmchip4 channel 0
static constexpr const char *M1_PWM_CHIP = "/sys/class/pwm/pwmchip8";
static constexpr int M1_PWM_CHANNEL = 1;
static constexpr const char *M2_PWM_CHIP = "/sys/class/pwm/pwmchip8";
static constexpr int M2_PWM_CHANNEL = 0;
static constexpr const char *M3_PWM_CHIP = "/sys/class/pwm/pwmchip4";
static constexpr int M3_PWM_CHANNEL = 3;
static constexpr const char *M4_PWM_CHIP = "/sys/class/pwm/pwmchip4";
static constexpr int M4_PWM_CHANNEL = 0;

static constexpr int PWM_PERIOD_US = 20000;    // 50Hz
static constexpr int PWM_STOP_US   = 1000;
static constexpr int PWM_IDLE_US   = 1050;
static constexpr int PWM_MIN_US    = 1000;
static constexpr int PWM_MAX_US_DEFAULT = 1600; // 第一次试飞前建议先用 1300~1500；确认后再提高

// 遥控器：IA6B i-BUS，当前接 GP3 / UART1_RX。实际 Linux 设备名可能需用环境变量覆盖。
static constexpr int IBUS_BAUD = 115200;
static constexpr int IBUS_FRAME_SIZE = 32;
static constexpr int RC_MIN = 1000;
static constexpr int RC_MID = 1500;
static constexpr int RC_MAX = 2000;
static constexpr int RC_TIMEOUT_MS = 500;
static constexpr int ARM_CH = 4;       // CH5，0-based index
static constexpr int THROTTLE_CH = 2;  // CH3，0-based index
static constexpr int ARM_THRESHOLD = 1500;
static constexpr int ARM_THROTTLE_LOW = 1100;

// MPU6050：当前稳定接法是 GP4/GP5 I2C，地址 0x68。
static constexpr int MPU6050_ADDR = 0x68;
static constexpr float GYRO_SCALE_500DPS = 65.5f;  // raw / 65.5 = deg/s
static constexpr float ACC_SCALE_2G = 16384.0f;    // raw / 16384 = g
static constexpr float COMPLEMENTARY_ALPHA = 0.98f;
static constexpr int IMU_CALIB_SAMPLES = 600;
static constexpr int CONTROL_RATE_HZ = 100;

// BMP180/BMP280：你当前发现 0x77 有温度/气压设备。程序会自动识别 BMP180 或 BMP280。
static constexpr int BMP_ADDR_PRIMARY = 0x77;
static constexpr int BMP_ADDR_SECONDARY = 0x76;

// 电池电压检测：VoltageSensor + 外接 10k/20k 二级分压后接 GP26/ADC。
static constexpr float ADC_REF_VOLTAGE = 1.8f;
static constexpr float ADC_MAX_RAW = 4095.0f;
static constexpr float BATTERY_SCALE_DEFAULT = 7.5f; // 用万用表校准后可通过 DRONE_BATTERY_SCALE 覆盖
static constexpr float BAT_WARN_V = 10.8f;
static constexpr float BAT_LIMIT_V = 10.2f;
static constexpr float BAT_CRITICAL_V = 9.6f;

// 控制目标与 PID 初值。真正起飞前必须无桨验证方向并小幅调参。
static constexpr float MAX_ROLL_DEG = 15.0f;
static constexpr float MAX_PITCH_DEG = 15.0f;
static constexpr float MAX_YAW_RATE_DPS = 90.0f;
static constexpr float RC_DEADBAND_US = 20.0f;

static constexpr float ROLL_KP = 1.0f;
static constexpr float ROLL_KI = 0.0f;
static constexpr float ROLL_KD = 0.03f;
static constexpr float PITCH_KP = 1.0f;
static constexpr float PITCH_KI = 0.0f;
static constexpr float PITCH_KD = 0.03f;
static constexpr float YAW_KP = 1.0f;
static constexpr float YAW_KI = 0.0f;
static constexpr float YAW_KD = 0.0f;

static constexpr float ROLL_PITCH_OUTPUT_LIMIT_US = 250.0f;
static constexpr float YAW_OUTPUT_LIMIT_US = 150.0f;
static constexpr float PID_INTEGRAL_LIMIT = 100.0f;

// 姿态保护：倾角超过此值立即锁定。
static constexpr float MAX_SAFE_ANGLE_DEG = 45.0f;

// 符号修正：如果无桨手持测试时补偿方向反了，优先改这里，然后重新编译。
// 也可以通过环境变量 DRONE_ROLL_MIX_SIGN / DRONE_PITCH_MIX_SIGN / DRONE_YAW_MIX_SIGN 覆盖。
static constexpr float DEFAULT_ROLL_MIX_SIGN = 1.0f;
static constexpr float DEFAULT_PITCH_MIX_SIGN = 1.0f;
static constexpr float DEFAULT_YAW_MIX_SIGN = 1.0f;

// 常见串口候选；建议在 /root/drone_fc.env 中明确指定。
inline std::vector<std::string> default_ibus_ports() {
    return {"/dev/ttyS1", "/dev/ttyS2", "/dev/ttyS3", "/dev/ttyS4", "/dev/ttyS0"};
}
inline std::vector<std::string> default_bt_ports() {
    return {"/dev/ttyS4", "/dev/ttyS3", "/dev/ttyS2", "/dev/ttyS1", "/dev/ttyS0"};
}
inline std::vector<std::string> default_i2c_devs() {
    return {"/dev/i2c-0", "/dev/i2c-1", "/dev/i2c-2", "/dev/i2c-3"};
}

} // namespace drone

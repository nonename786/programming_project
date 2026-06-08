#include "battery.h"
#include "bmp_sensor.h"
#include "common.h"
#include "config.h"
#include "esc_pwm.h"
#include "mpu6050.h"
#include "pid.h"
#include "rc_ibus.h"
#include "telemetry.h"

#include <array>
#include <csignal>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

using namespace drone;

namespace {

volatile std::sig_atomic_t g_running = 1;

void on_signal(int) {
    g_running = 0;
}

enum class Mode {
    Help,
    FlyBasic,
    RcMotorTest,
    ImuTest,
    IBusTest,
    EscTest,
    PwmStop,
};

struct Args {
    Mode mode = Mode::Help;
    bool dry_run = false;
    bool no_bt = false;
    bool no_bmp = false;
    bool no_battery = false;
    bool understand_no_props = false;

    std::string ibus_port;
    std::string bt_port;
    std::string i2c_dev;
    std::string adc_path;
    std::string log_path = "/root/drone_fc_telemetry.csv";

    int ibus_baud = 115200;
    int bt_baud = 9600;
    int max_pwm = 1550;
    int esc_test_us = 1300;
};

void print_help() {
    std::cout <<
R"(drone_fc - Milk-V Duo 256 basic flight controller

Modes:
  --fly-basic / --fly        Basic stabilized flight: iBUS + MPU6050 + PID + PWM + Bluetooth
  --rc-motor-test            No-prop RC direct motor test, no PID stabilization
  --imu-test                 Test MPU6050 attitude
  --ibus-test                Test IA6B iBUS channels
  --esc-test --i-understand-no-props --esc-us 1300
                             No-prop single motor test M1~M4
  --pwm-stop                 Set all motors to 1000us

Common options:
  --ibus-port /dev/ttyS1
  --bt-port /dev/ttyS2
  --bt-baud 9600
  --i2c-dev /dev/i2c-1
  --max-pwm 1550
  --no-bmp --no-battery

Safety:
  CH5 off = motors 1000us immediately.
  Receiver lost = motors 1000us immediately.
  Arm requires CH5 on and CH3 low first.
  Roll/Pitch angle too large = motors 1000us immediately.
)";
}

Args parse_args(int argc, char **argv) {
    Args a;
    a.ibus_port = getenv_str("DRONE_IBUS_PORT", "");
    a.ibus_baud = getenv_int("DRONE_IBUS_BAUD", 115200);
    a.bt_port = getenv_str("DRONE_BT_PORT", "");
    a.bt_baud = getenv_int("DRONE_BT_BAUD", 9600);
    a.i2c_dev = getenv_str("DRONE_I2C_DEV", "");
    a.adc_path = getenv_str("DRONE_ADC_PATH", "");
    a.log_path = getenv_str("DRONE_LOG_PATH", a.log_path);
    a.max_pwm = getenv_int("DRONE_MAX_PWM", 1550);
    a.esc_test_us = getenv_int("DRONE_ESC_TEST_US", 1300);

    for (int i = 1; i < argc; ++i) {
        std::string s = argv[i];
        auto need_value = [&](const char *name) -> std::string {
            if (i + 1 >= argc) {
                std::cerr << "Missing value after " << name << "\n";
                return "";
            }
            return argv[++i];
        };

        if (s == "--fly" || s == "--fly-basic") a.mode = Mode::FlyBasic;
        else if (s == "--rc-motor-test") a.mode = Mode::RcMotorTest;
        else if (s == "--imu-test") a.mode = Mode::ImuTest;
        else if (s == "--ibus-test") a.mode = Mode::IBusTest;
        else if (s == "--esc-test") a.mode = Mode::EscTest;
        else if (s == "--pwm-stop") a.mode = Mode::PwmStop;
        else if (s == "--dry-run") a.dry_run = true;
        else if (s == "--no-bt") a.no_bt = true;
        else if (s == "--no-bmp") a.no_bmp = true;
        else if (s == "--no-battery") a.no_battery = true;
        else if (s == "--i-understand-no-props") a.understand_no_props = true;
        else if (s == "--ibus-port") a.ibus_port = need_value("--ibus-port");
        else if (s == "--ibus-baud") a.ibus_baud = std::stoi(need_value("--ibus-baud"));
        else if (s == "--bt-port") a.bt_port = need_value("--bt-port");
        else if (s == "--bt-baud") a.bt_baud = std::stoi(need_value("--bt-baud"));
        else if (s == "--i2c-dev") a.i2c_dev = need_value("--i2c-dev");
        else if (s == "--adc-path") a.adc_path = need_value("--adc-path");
        else if (s == "--max-pwm") a.max_pwm = std::stoi(need_value("--max-pwm"));
        else if (s == "--esc-us") a.esc_test_us = std::stoi(need_value("--esc-us"));
        else if (s == "--log-path") a.log_path = need_value("--log-path");
        else if (s == "--help" || s == "-h") a.mode = Mode::Help;
        else std::cerr << "Unknown option: " << s << "\n";
    }

    a.max_pwm = clamp_int(a.max_pwm, PWM_IDLE_US, 2000);
    a.esc_test_us = clamp_int(a.esc_test_us, 1000, 1500);
    return a;
}

std::vector<std::string> i2c_devs_from_args(const Args &a) {
    if (!a.i2c_dev.empty()) return {a.i2c_dev};
    return split_csv_env("DRONE_I2C_DEVS", default_i2c_devs());
}

std::vector<std::string> ibus_ports_from_args(const Args &a) {
    if (!a.ibus_port.empty()) return {a.ibus_port};
    return split_csv_env("DRONE_IBUS_PORTS", default_ibus_ports());
}

std::vector<std::string> bt_ports_from_args(const Args &a) {
    if (!a.bt_port.empty()) return {a.bt_port};
    return split_csv_env("DRONE_BT_PORTS", default_bt_ports());
}

bool init_mpu(MPU6050 &mpu, const Args &a, bool calibrate) {
    if (!mpu.open_auto(i2c_devs_from_args(a), MPU6050_ADDR)) {
        std::cerr << "MPU6050 not found. Check GP4/GP5 I2C pinmux and /dev/i2c-X.\n";
        return false;
    }
    if (!mpu.init()) {
        std::cerr << "MPU6050 init failed on " << mpu.dev_name() << "\n";
        return false;
    }
    std::cout << "MPU6050 OK on " << mpu.dev_name() << " addr 0x68\n";
    if (calibrate) {
        std::cout << "Calibrating gyro: keep drone still...\n";
        if (!mpu.calibrate_gyro(IMU_CALIB_SAMPLES)) {
            std::cerr << "Gyro calibration failed.\n";
            return false;
        }
        std::cout << "Gyro bias: gx=" << mpu.gyro_bias_x()
                  << " gy=" << mpu.gyro_bias_y()
                  << " gz=" << mpu.gyro_bias_z() << " deg/s\n";
    }
    return true;
}

bool init_rc(IBusReceiver &rc, const Args &a) {
    if (!rc.open_first(ibus_ports_from_args(a), a.ibus_baud)) {
        std::cerr << "IBUS serial open failed. Set --ibus-port.\n";
        return false;
    }
    std::cout << "IBUS opened on " << rc.port_name() << " @ " << a.ibus_baud << "\n";
    return true;
}

bool channel_sane(uint16_t ch) {
    return ch >= 800 && ch <= 2200;
}

bool rc_is_ok(const RcState &rc_state) {
    if (!rc_state.valid) return false;
    if (now_ms() - rc_state.last_frame_ms >= RC_TIMEOUT_MS) return false;
    for (int i = 0; i < 6; ++i) {
        if (!channel_sane(rc_state.ch[i])) return false;
    }
    return true;
}

float rc_centered(uint16_t ch) {
    float v = clamp_float(static_cast<float>(ch), RC_MIN, RC_MAX);
    float c = v - RC_MID;
    return apply_deadband(c, RC_DEADBAND_US);
}

float rc_to_angle(uint16_t ch, float max_deg) {
    return map_float(rc_centered(ch), -500.0f, 500.0f, -max_deg, max_deg);
}

float rc_to_yaw_rate(uint16_t ch, float max_dps) {
    return map_float(rc_centered(ch), -500.0f, 500.0f, -max_dps, max_dps);
}

int rc_direct_base_pwm(uint16_t ch3, int active_max_pwm) {
    int ch = clamp_int(static_cast<int>(ch3), RC_MIN, RC_MAX);
    if (ch < 1030) return PWM_STOP_US;
    float t = static_cast<float>(ch - RC_MIN) / static_cast<float>(RC_MAX - RC_MIN);
    t = clamp_float(t, 0.0f, 1.0f);
    return static_cast<int>(PWM_STOP_US + t * (active_max_pwm - PWM_STOP_US));
}

int flight_base_pwm(uint16_t ch3, int active_max_pwm) {
    int ch = clamp_int(static_cast<int>(ch3), RC_MIN, RC_MAX);
    const int throttle_start_ch = getenv_int("DRONE_FLIGHT_THROTTLE_START_CH", 1060);
    const int motor_start_pwm = getenv_int("DRONE_FLIGHT_MOTOR_START_PWM", 1220);
    if (ch < throttle_start_ch) return PWM_STOP_US;

    float t = static_cast<float>(ch - throttle_start_ch) / static_cast<float>(RC_MAX - throttle_start_ch);
    t = clamp_float(t, 0.0f, 1.0f);
    // Gentle curve, but always jump over the ESC start area when throttle is raised.
    float curved = 0.75f * t + 0.25f * t * t;
    return static_cast<int>(motor_start_pwm + curved * (active_max_pwm - motor_start_pwm));
}

std::string readable_line(const char *mode,
                          const char *status,
                          bool armed,
                          bool rc_ok,
                          bool imu_ok,
                          const RcState &rc,
                          const Attitude &att,
                          int base,
                          float r, float p, float y,
                          const MotorOutputs &m) {
    auto ch = [&](int i) -> int { return rc.valid ? static_cast<int>(rc.ch[static_cast<size_t>(i)]) : 0; };
    std::ostringstream ss;
    ss.setf(std::ios::fixed);
    ss.precision(1);
    ss << "MODE=" << mode
       << " ARM=" << (armed ? 1 : 0)
       << " STATUS=" << status
       << " RC=" << (rc_ok ? 1 : 0)
       << " IMU=" << (imu_ok ? 1 : 0)
       << " CH1=" << ch(0)
       << " CH2=" << ch(1)
       << " CH3=" << ch(2)
       << " CH4=" << ch(3)
       << " CH5=" << ch(4)
       << " BASE=" << base
       << " R=" << r
       << " P=" << p
       << " Y=" << y
       << " M1=" << m.m1
       << " M2=" << m.m2
       << " M3=" << m.m3
       << " M4=" << m.m4
       << " ROLL=" << att.roll_deg
       << " PITCH=" << att.pitch_deg
       << " YAW=" << att.yaw_deg;
    return ss.str();
}

int run_imu_test(const Args &a) {
    MPU6050 mpu;
    if (!init_mpu(mpu, a, true)) return 2;
    Attitude att{};
    ImuScaled imu{};
    uint64_t last = now_us();
    while (g_running) {
        uint64_t t = now_us();
        float dt = static_cast<float>(t - last) / 1000000.0f;
        last = t;
        if (mpu.update(dt, att, imu)) {
            std::cout << "roll=" << att.roll_deg << " pitch=" << att.pitch_deg << " yaw=" << att.yaw_deg
                      << " ax=" << imu.ax_g << " ay=" << imu.ay_g << " az=" << imu.az_g
                      << " gx=" << imu.gx_dps << " gy=" << imu.gy_dps << " gz=" << imu.gz_dps << "\n";
        }
        sleep_us(50000);
    }
    return 0;
}

int run_ibus_test(const Args &a) {
    IBusReceiver rc;
    if (!init_rc(rc, a)) return 2;
    RcState state{};
    while (g_running) {
        rc.poll(state);
        bool ok = rc_is_ok(state);
        std::cout << (ok ? "RC_OK" : "RC_WAIT");
        if (state.valid) {
            for (int i = 0; i < 8; ++i) std::cout << " CH" << (i + 1) << '=' << state.ch[i];
        }
        std::cout << "\n";
        sleep_us(100000);
    }
    return 0;
}

int run_pwm_stop(const Args &a) {
    EscPwm pwm(a.dry_run);
    if (!pwm.init(PWM_PERIOD_US)) return 2;
    pwm.stop_all();
    std::cout << "PWM initialized and all motors set to 1000us. " << pwm.status() << "\n";
    return 0;
}

int run_esc_test(const Args &a) {
    if (!a.understand_no_props) {
        std::cerr << "ESC test refused. Remove all propellers and add --i-understand-no-props.\n";
        return 2;
    }
    std::cout << "WARNING: ESC test mode. Make sure all propellers are removed.\n";
    std::cout << "ESC test pulse = " << a.esc_test_us << "us.\n";

    EscPwm pwm(a.dry_run);
    if (!pwm.init(PWM_PERIOD_US)) return 2;
    std::cout << pwm.status() << "\n";
    pwm.stop_all();
    sleep_us(2000000);

    const int u = clamp_int(a.esc_test_us, 1000, 1500);
    const char *names[4] = {"M1 left front", "M2 right front", "M3 left rear", "M4 right rear"};
    for (int i = 0; i < 4 && g_running; ++i) {
        MotorOutputs out{1000,1000,1000,1000};
        if (i == 0) out.m1 = u;
        if (i == 1) out.m2 = u;
        if (i == 2) out.m3 = u;
        if (i == 3) out.m4 = u;
        std::cout << "Testing " << names[i] << " at " << u << "us.\n";
        pwm.write_us(out);
        sleep_us(2500000);
        pwm.stop_all();
        sleep_us(1000000);
    }
    pwm.stop_all();
    return 0;
}

int run_rc_motor_test(const Args &a) {
    std::cout << "RC MOTOR TEST MODE: NO PROPS. This is not stabilized flight.\n";

    Telemetry tel;
    tel.set_log_file(a.log_path);
    tel.set_stdout_enabled(true);
    if (!a.no_bt) {
        bool bt_ok = false;
        if (!a.bt_port.empty()) bt_ok = tel.open_bluetooth(a.bt_port, a.bt_baud);
        else bt_ok = tel.open_bluetooth_first(bt_ports_from_args(a), a.bt_baud);
        if (bt_ok) std::cout << "Bluetooth telemetry opened on " << tel.bt_port() << " @ " << a.bt_baud << "\n";
        else std::cerr << "Bluetooth not opened.\n";
    }

    EscPwm pwm(a.dry_run);
    if (!pwm.init(PWM_PERIOD_US)) return 2;
    pwm.stop_all();

    MPU6050 mpu;
    bool imu_ok = init_mpu(mpu, a, false);
    Attitude att{};
    ImuScaled imu{};

    IBusReceiver rc;
    if (!init_rc(rc, a)) return 2;

    const float roll_sign = getenv_float("DRONE_ROLL_MIX_SIGN", 1.0f);
    const float pitch_sign = getenv_float("DRONE_PITCH_MIX_SIGN", 1.0f);
    const float yaw_sign = getenv_float("DRONE_YAW_MIX_SIGN", 0.0f);
    const int mix_limit = getenv_int("DRONE_RC_MIX_LIMIT_US", 100);
    const int yaw_limit = getenv_int("DRONE_RC_YAW_MIX_LIMIT_US", 0);

    bool armed = false;
    RcState rc_state{};
    MotorOutputs motors{1000,1000,1000,1000};
    uint64_t last_loop_us = now_us();
    uint64_t next_loop_us = last_loop_us;
    uint64_t last_tel_ms = 0;

    tel.send_text("RC_MOTOR_TEST_READY CH5=ARM CH3=THROTTLE");

    while (g_running) {
        uint64_t loop_us = now_us();
        float dt = static_cast<float>(loop_us - last_loop_us) / 1000000.0f;
        last_loop_us = loop_us;
        if (dt <= 0.0f || dt > 0.05f) dt = 0.01f;

        rc.poll(rc_state);
        bool rc_ok = rc_is_ok(rc_state);
        if (imu_ok) imu_ok = mpu.update(dt, att, imu);

        bool arm_switch = rc_ok && rc_state.ch[ARM_CH] > ARM_THRESHOLD;
        if (!rc_ok || !arm_switch) armed = false;
        else if (!armed && rc_state.ch[THROTTLE_CH] < ARM_THROTTLE_LOW) armed = true;

        int base = 1000;
        float R = 0.0f, P = 0.0f, Y = 0.0f;
        const char *status = "LOCKED";

        if (!armed) {
            motors = {1000,1000,1000,1000};
            status = rc_ok ? "LOCKED_CH5_OFF" : "RC_LOST";
        } else {
            base = rc_direct_base_pwm(rc_state.ch[THROTTLE_CH], a.max_pwm);
            R = roll_sign * map_float(rc_centered(rc_state.ch[0]), -500.0f, 500.0f, -static_cast<float>(mix_limit), static_cast<float>(mix_limit));
            P = pitch_sign * map_float(rc_centered(rc_state.ch[1]), -500.0f, 500.0f, -static_cast<float>(mix_limit), static_cast<float>(mix_limit));
            Y = yaw_sign * map_float(rc_centered(rc_state.ch[3]), -500.0f, 500.0f, -static_cast<float>(yaw_limit), static_cast<float>(yaw_limit));

            motors.m1 = clamp_int(static_cast<int>(base + P + R - Y), PWM_MIN_US, a.max_pwm);
            motors.m2 = clamp_int(static_cast<int>(base + P - R + Y), PWM_MIN_US, a.max_pwm);
            motors.m3 = clamp_int(static_cast<int>(base - P + R + Y), PWM_MIN_US, a.max_pwm);
            motors.m4 = clamp_int(static_cast<int>(base - P - R - Y), PWM_MIN_US, a.max_pwm);
            status = "RC_DIRECT_MOTOR";
        }

        pwm.write_us(motors);

        uint64_t t_ms = now_ms();
        if (t_ms - last_tel_ms >= static_cast<uint64_t>(getenv_int("DRONE_TELEMETRY_MS", 200))) {
            tel.send_text(readable_line("RC_TEST", status, armed, rc_ok, imu_ok, rc_state, att, base, R, P, Y, motors));
            last_tel_ms = t_ms;
        }

        next_loop_us += 1000000ULL / CONTROL_RATE_HZ;
        uint64_t nowu = now_us();
        if (next_loop_us < nowu) next_loop_us = nowu;
        sleep_until_us(next_loop_us);
    }

    pwm.stop_all();
    tel.send_text("RC_MOTOR_TEST_STOP_MOTORS_1000US");
    return 0;
}

int run_fly_basic(const Args &a) {
    std::cout << "BASIC FLIGHT MODE. Do all no-prop direction checks before installing propellers.\n";

    Telemetry tel;
    tel.set_log_file(a.log_path);
    tel.set_stdout_enabled(true);
    if (!a.no_bt) {
        bool bt_ok = false;
        if (!a.bt_port.empty()) bt_ok = tel.open_bluetooth(a.bt_port, a.bt_baud);
        else bt_ok = tel.open_bluetooth_first(bt_ports_from_args(a), a.bt_baud);
        if (bt_ok) std::cout << "Bluetooth telemetry opened on " << tel.bt_port() << " @ " << a.bt_baud << "\n";
        else std::cerr << "Bluetooth not opened.\n";
    }

    EscPwm pwm(a.dry_run);
    if (!pwm.init(PWM_PERIOD_US)) return 2;
    pwm.stop_all();

    MPU6050 mpu;
    if (!init_mpu(mpu, a, true)) {
        pwm.stop_all();
        tel.send_text("IMU_FAILED_MOTORS_STOPPED");
        return 2;
    }

    IBusReceiver rc;
    if (!init_rc(rc, a)) {
        pwm.stop_all();
        tel.send_text("IBUS_FAILED_MOTORS_STOPPED");
        return 2;
    }

    const float roll_sign = getenv_float("DRONE_ROLL_MIX_SIGN", 1.0f);
    const float pitch_sign = getenv_float("DRONE_PITCH_MIX_SIGN", 1.0f);
    const float yaw_sign = getenv_float("DRONE_YAW_MIX_SIGN", 1.0f);
    const float max_roll_deg = getenv_float("DRONE_MAX_ROLL_SET_DEG", 10.0f);
    const float max_pitch_deg = getenv_float("DRONE_MAX_PITCH_SET_DEG", 10.0f);
    const float max_yaw_dps = getenv_float("DRONE_MAX_YAW_RATE_DPS", 60.0f);
    const float max_safe_angle = getenv_float("DRONE_MAX_SAFE_ANGLE", 45.0f);

    PID pid_roll(getenv_float("DRONE_ROLL_KP", 1.0f), getenv_float("DRONE_ROLL_KI", 0.0f), getenv_float("DRONE_ROLL_KD", 0.03f),
                 PID_INTEGRAL_LIMIT, getenv_float("DRONE_ROLL_OUTPUT_LIMIT_US", 180.0f));
    PID pid_pitch(getenv_float("DRONE_PITCH_KP", 1.0f), getenv_float("DRONE_PITCH_KI", 0.0f), getenv_float("DRONE_PITCH_KD", 0.03f),
                  PID_INTEGRAL_LIMIT, getenv_float("DRONE_PITCH_OUTPUT_LIMIT_US", 180.0f));
    PID pid_yaw(getenv_float("DRONE_YAW_KP", 0.5f), getenv_float("DRONE_YAW_KI", 0.0f), getenv_float("DRONE_YAW_KD", 0.0f),
                PID_INTEGRAL_LIMIT, getenv_float("DRONE_YAW_OUTPUT_LIMIT_US", 100.0f));

    bool armed = false;
    bool was_armed = false;
    RcState rc_state{};
    Attitude att{};
    ImuScaled imu{};
    MotorOutputs motors{1000,1000,1000,1000};
    uint64_t last_loop_us = now_us();
    uint64_t next_loop_us = last_loop_us;
    uint64_t last_tel_ms = 0;

    tel.send_text("FLY_BASIC_READY CH5=ARM CH3=THROTTLE");

    while (g_running) {
        uint64_t loop_us = now_us();
        float dt = static_cast<float>(loop_us - last_loop_us) / 1000000.0f;
        last_loop_us = loop_us;
        if (dt <= 0.0f || dt > 0.05f) dt = 0.01f;

        rc.poll(rc_state);
        bool rc_ok = rc_is_ok(rc_state);
        bool imu_ok = mpu.update(dt, att, imu);

        bool angle_safe = std::fabs(att.roll_deg) < max_safe_angle && std::fabs(att.pitch_deg) < max_safe_angle;
        bool arm_switch = rc_ok && rc_state.ch[ARM_CH] > ARM_THRESHOLD;
        bool throttle_low = rc_ok && rc_state.ch[THROTTLE_CH] < ARM_THROTTLE_LOW;

        const char *status = "LOCKED";
        if (!rc_ok) {
            armed = false;
            status = "RC_LOST";
        } else if (!imu_ok) {
            armed = false;
            status = "IMU_FAIL";
        } else if (!angle_safe) {
            armed = false;
            status = "ANGLE_FAILSAFE";
        } else if (!arm_switch) {
            armed = false;
            status = "LOCKED_CH5_OFF";
        } else if (!armed && !throttle_low) {
            armed = false;
            status = "WAIT_THROTTLE_LOW";
        } else if (!armed && throttle_low) {
            armed = true;
            pid_roll.reset();
            pid_pitch.reset();
            pid_yaw.reset();
            tel.send_text("ARMED_FLY_BASIC");
            status = "ARMED";
        }

        int base = 1000;
        float R = 0.0f, P = 0.0f, Y = 0.0f;

        if (!armed) {
            pid_roll.reset();
            pid_pitch.reset();
            pid_yaw.reset();
            motors = {1000,1000,1000,1000};
            pwm.write_us(motors);
        } else {
            base = flight_base_pwm(rc_state.ch[THROTTLE_CH], a.max_pwm);
            float roll_set = rc_to_angle(rc_state.ch[0], max_roll_deg);
            float pitch_set = rc_to_angle(rc_state.ch[1], max_pitch_deg);
            float yaw_rate_set = rc_to_yaw_rate(rc_state.ch[3], max_yaw_dps);

            if (rc_state.ch[THROTTLE_CH] < 1050) {
                pid_roll.reset();
                pid_pitch.reset();
                pid_yaw.reset();
            }

            R = roll_sign * pid_roll.update(roll_set, att.roll_deg, dt);
            P = pitch_sign * pid_pitch.update(pitch_set, att.pitch_deg, dt);
            Y = yaw_sign * pid_yaw.update(yaw_rate_set, imu.gz_dps, dt);

            motors.m1 = clamp_int(static_cast<int>(base + P + R - Y), PWM_MIN_US, a.max_pwm);
            motors.m2 = clamp_int(static_cast<int>(base + P - R + Y), PWM_MIN_US, a.max_pwm);
            motors.m3 = clamp_int(static_cast<int>(base - P + R + Y), PWM_MIN_US, a.max_pwm);
            motors.m4 = clamp_int(static_cast<int>(base - P - R - Y), PWM_MIN_US, a.max_pwm);
            pwm.write_us(motors);
            status = "FLY_BASIC";
        }

        if (was_armed && !armed) {
            pwm.stop_all();
            tel.send_text(std::string("DISARMED_") + status);
        }
        was_armed = armed;

        uint64_t t_ms = now_ms();
        if (t_ms - last_tel_ms >= static_cast<uint64_t>(getenv_int("DRONE_TELEMETRY_MS", 200))) {
            tel.send_text(readable_line("FLY", status, armed, rc_ok, imu_ok, rc_state, att, base, R, P, Y, motors));
            last_tel_ms = t_ms;
        }

        next_loop_us += 1000000ULL / CONTROL_RATE_HZ;
        uint64_t nowu = now_us();
        if (next_loop_us < nowu) next_loop_us = nowu;
        sleep_until_us(next_loop_us);
    }

    pwm.stop_all();
    tel.send_text("FLY_BASIC_STOP_MOTORS_1000US");
    return 0;
}

} // namespace

int main(int argc, char **argv) {
    std::signal(SIGINT, on_signal);
    std::signal(SIGTERM, on_signal);

    Args args = parse_args(argc, argv);
    switch (args.mode) {
        case Mode::Help: print_help(); return 0;
        case Mode::FlyBasic: return run_fly_basic(args);
        case Mode::RcMotorTest: return run_rc_motor_test(args);
        case Mode::ImuTest: return run_imu_test(args);
        case Mode::IBusTest: return run_ibus_test(args);
        case Mode::EscTest: return run_esc_test(args);
        case Mode::PwmStop: return run_pwm_stop(args);
        default: print_help(); return 0;
    }
}


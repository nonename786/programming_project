#include "mpu6050.h"

#include "common.h"
#include "config.h"

#include <cmath>
#include <fcntl.h>
#include <iostream>
#include <linux/i2c-dev.h>
#include <sys/ioctl.h>
#include <unistd.h>

namespace drone {

static int16_t be16(const uint8_t *p) {
    return static_cast<int16_t>((static_cast<uint16_t>(p[0]) << 8) | p[1]);
}

MPU6050::MPU6050() = default;
MPU6050::~MPU6050() { close_device(); }

bool MPU6050::set_slave() {
    return fd_ >= 0 && ioctl(fd_, I2C_SLAVE, addr_) >= 0;
}

bool MPU6050::open_auto(const std::vector<std::string> &i2c_devs, int addr) {
    for (const auto &dev : i2c_devs) {
        if (open_device(dev, addr)) {
            uint8_t who = 0;
            if (read_reg(0x75, who) && (who == 0x68 || who == 0x69 || who == 0x70)) {
                return true;
            }
            close_device();
        }
    }
    return false;
}

bool MPU6050::open_device(const std::string &dev, int addr) {
    close_device();
    int fd = ::open(dev.c_str(), O_RDWR);
    if (fd < 0) return false;
    fd_ = fd;
    addr_ = addr;
    dev_name_ = dev;
    if (!set_slave()) {
        close_device();
        return false;
    }
    return true;
}

void MPU6050::close_device() {
    if (fd_ >= 0) ::close(fd_);
    fd_ = -1;
    dev_name_.clear();
    initialized_ = false;
}

bool MPU6050::write_reg(uint8_t reg, uint8_t val) {
    if (!set_slave()) return false;
    uint8_t data[2] = {reg, val};
    return ::write(fd_, data, 2) == 2;
}

bool MPU6050::read_regs(uint8_t reg, uint8_t *buf, int len) {
    if (!set_slave()) return false;
    if (::write(fd_, &reg, 1) != 1) return false;
    return ::read(fd_, buf, len) == len;
}

bool MPU6050::read_reg(uint8_t reg, uint8_t &val) {
    return read_regs(reg, &val, 1);
}

bool MPU6050::init() {
    if (fd_ < 0) return false;
    // 唤醒 MPU6050，配置 100Hz 以上数据读取。
    bool ok = true;
    ok &= write_reg(0x6B, 0x00); // PWR_MGMT_1: wake up, internal clock
    sleep_us(100000);
    ok &= write_reg(0x1A, 0x03); // CONFIG: DLPF 44Hz/42Hz
    ok &= write_reg(0x19, 0x04); // SMPLRT_DIV: 1kHz/(1+4)=200Hz
    ok &= write_reg(0x1B, 0x08); // GYRO_CONFIG: ±500 dps
    ok &= write_reg(0x1C, 0x00); // ACCEL_CONFIG: ±2g
    initialized_ = ok;
    return ok;
}

bool MPU6050::read_raw(ImuRaw &raw) {
    uint8_t b[14]{};
    if (!read_regs(0x3B, b, 14)) return false;
    raw.ax = be16(&b[0]);
    raw.ay = be16(&b[2]);
    raw.az = be16(&b[4]);
    raw.gx = be16(&b[8]);
    raw.gy = be16(&b[10]);
    raw.gz = be16(&b[12]);
    return true;
}

bool MPU6050::read_scaled(ImuScaled &out) {
    ImuRaw raw{};
    if (!read_raw(raw)) return false;
    out.ax_g = static_cast<float>(raw.ax) / ACC_SCALE_2G;
    out.ay_g = static_cast<float>(raw.ay) / ACC_SCALE_2G;
    out.az_g = static_cast<float>(raw.az) / ACC_SCALE_2G;
    out.gx_dps = static_cast<float>(raw.gx) / GYRO_SCALE_500DPS - gyro_bias_x_;
    out.gy_dps = static_cast<float>(raw.gy) / GYRO_SCALE_500DPS - gyro_bias_y_;
    out.gz_dps = static_cast<float>(raw.gz) / GYRO_SCALE_500DPS - gyro_bias_z_;
    return true;
}

bool MPU6050::calibrate_gyro(int samples) {
    if (!initialized_) return false;
    double sx = 0, sy = 0, sz = 0;
    int count = 0;
    for (int i = 0; i < samples; ++i) {
        ImuRaw raw{};
        if (read_raw(raw)) {
            sx += static_cast<double>(raw.gx) / GYRO_SCALE_500DPS;
            sy += static_cast<double>(raw.gy) / GYRO_SCALE_500DPS;
            sz += static_cast<double>(raw.gz) / GYRO_SCALE_500DPS;
            ++count;
        }
        sleep_us(5000);
    }
    if (count < samples / 2) return false;
    gyro_bias_x_ = static_cast<float>(sx / count);
    gyro_bias_y_ = static_cast<float>(sy / count);
    gyro_bias_z_ = static_cast<float>(sz / count);
    return true;
}

bool MPU6050::update(float dt_s, Attitude &att, ImuScaled &scaled) {
    if (!read_scaled(scaled)) return false;
    if (dt_s <= 0.0f || dt_s > 0.1f) dt_s = 0.01f;

    const float rad_to_deg = 57.2957795f;
    float roll_acc = std::atan2(scaled.ay_g, scaled.az_g) * rad_to_deg;
    float pitch_acc = std::atan2(-scaled.ax_g, std::sqrt(scaled.ay_g * scaled.ay_g + scaled.az_g * scaled.az_g)) * rad_to_deg;

    att.roll_deg = COMPLEMENTARY_ALPHA * (att.roll_deg + scaled.gx_dps * dt_s) +
                   (1.0f - COMPLEMENTARY_ALPHA) * roll_acc;
    att.pitch_deg = COMPLEMENTARY_ALPHA * (att.pitch_deg + scaled.gy_dps * dt_s) +
                    (1.0f - COMPLEMENTARY_ALPHA) * pitch_acc;
    att.yaw_deg += scaled.gz_dps * dt_s;

    if (att.yaw_deg > 180.0f) att.yaw_deg -= 360.0f;
    if (att.yaw_deg < -180.0f) att.yaw_deg += 360.0f;
    return true;
}

} // namespace drone

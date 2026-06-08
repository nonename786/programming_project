#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace drone {

struct ImuRaw {
    int16_t ax = 0, ay = 0, az = 0;
    int16_t gx = 0, gy = 0, gz = 0;
};

struct ImuScaled {
    float ax_g = 0, ay_g = 0, az_g = 0;
    float gx_dps = 0, gy_dps = 0, gz_dps = 0;
};

struct Attitude {
    float roll_deg = 0;
    float pitch_deg = 0;
    float yaw_deg = 0;
};

class MPU6050 {
public:
    MPU6050();
    ~MPU6050();

    bool open_auto(const std::vector<std::string> &i2c_devs, int addr);
    bool open_device(const std::string &dev, int addr);
    void close_device();
    bool is_open() const { return fd_ >= 0; }
    const std::string &dev_name() const { return dev_name_; }

    bool init();
    bool read_raw(ImuRaw &raw);
    bool read_scaled(ImuScaled &out);
    bool calibrate_gyro(int samples);
    bool update(float dt_s, Attitude &att, ImuScaled &scaled);

    float gyro_bias_x() const { return gyro_bias_x_; }
    float gyro_bias_y() const { return gyro_bias_y_; }
    float gyro_bias_z() const { return gyro_bias_z_; }

private:
    bool write_reg(uint8_t reg, uint8_t val);
    bool read_regs(uint8_t reg, uint8_t *buf, int len);
    bool read_reg(uint8_t reg, uint8_t &val);
    bool set_slave();

    int fd_ = -1;
    int addr_ = 0x68;
    std::string dev_name_;
    float gyro_bias_x_ = 0;
    float gyro_bias_y_ = 0;
    float gyro_bias_z_ = 0;
    bool initialized_ = false;
};

} // namespace drone

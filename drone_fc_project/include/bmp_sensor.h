#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace drone {

struct BmpReading {
    float temperature_c = 0;
    float pressure_pa = 0;
    float altitude_m = 0;
    bool valid = false;
};

enum class BmpType {
    None,
    BMP180,
    BMP280,
    BME280
};

class BmpSensor {
public:
    BmpSensor();
    ~BmpSensor();

    bool open_auto(const std::vector<std::string> &i2c_devs);
    bool open_device(const std::string &dev, int addr);
    void close_device();
    bool is_open() const { return fd_ >= 0 && type_ != BmpType::None; }
    const std::string &dev_name() const { return dev_name_; }
    int addr() const { return addr_; }
    BmpType type() const { return type_; }
    std::string type_name() const;

    bool init();
    bool read(BmpReading &out);
    void set_sea_level_pressure(float p0_pa) { sea_level_pressure_pa_ = p0_pa; }
    float sea_level_pressure() const { return sea_level_pressure_pa_; }

private:
    bool set_slave();
    bool write_reg(uint8_t reg, uint8_t val);
    bool read_regs(uint8_t reg, uint8_t *buf, int len);
    bool read_reg(uint8_t reg, uint8_t &val);

    bool init_bmp280();
    bool read_bmp280(BmpReading &out);
    bool read_calib_bmp280();

    bool init_bmp180();
    bool read_bmp180(BmpReading &out);
    bool read_calib_bmp180();

    int fd_ = -1;
    int addr_ = 0x77;
    std::string dev_name_;
    BmpType type_ = BmpType::None;
    float sea_level_pressure_pa_ = 101325.0f;

    // BMP280 compensation parameters
    uint16_t dig_T1_ = 0;
    int16_t dig_T2_ = 0, dig_T3_ = 0;
    uint16_t dig_P1_ = 0;
    int16_t dig_P2_ = 0, dig_P3_ = 0, dig_P4_ = 0, dig_P5_ = 0, dig_P6_ = 0, dig_P7_ = 0, dig_P8_ = 0, dig_P9_ = 0;
    int32_t t_fine_ = 0;

    // BMP180 compensation parameters
    int16_t ac1_ = 0, ac2_ = 0, ac3_ = 0, b1_ = 0, b2_ = 0, mb_ = 0, mc_ = 0, md_ = 0;
    uint16_t ac4_ = 0, ac5_ = 0, ac6_ = 0;
};

} // namespace drone

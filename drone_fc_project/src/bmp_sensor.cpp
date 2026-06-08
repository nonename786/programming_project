#include "bmp_sensor.h"

#include "common.h"
#include "config.h"

#include <cmath>
#include <fcntl.h>
#include <iostream>
#include <linux/i2c-dev.h>
#include <sys/ioctl.h>
#include <unistd.h>

namespace drone {

static uint16_t le_u16(const uint8_t *p) { return static_cast<uint16_t>(p[0]) | (static_cast<uint16_t>(p[1]) << 8); }
static int16_t le_s16(const uint8_t *p) { return static_cast<int16_t>(le_u16(p)); }
static uint16_t be_u16(const uint8_t *p) { return static_cast<uint16_t>(p[1]) | (static_cast<uint16_t>(p[0]) << 8); }
static int16_t be_s16(const uint8_t *p) { return static_cast<int16_t>(be_u16(p)); }

BmpSensor::BmpSensor() = default;
BmpSensor::~BmpSensor() { close_device(); }

bool BmpSensor::set_slave() { return fd_ >= 0 && ioctl(fd_, I2C_SLAVE, addr_) >= 0; }

bool BmpSensor::open_auto(const std::vector<std::string> &i2c_devs) {
    for (const auto &dev : i2c_devs) {
        for (int addr : {BMP_ADDR_PRIMARY, BMP_ADDR_SECONDARY}) {
            if (open_device(dev, addr)) return true;
        }
    }
    return false;
}

bool BmpSensor::open_device(const std::string &dev, int addr) {
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
    uint8_t id = 0;
    if (!read_reg(0xD0, id)) {
        close_device();
        return false;
    }
    if (id == 0x55) {
        type_ = BmpType::BMP180;
    } else if (id == 0x58) {
        type_ = BmpType::BMP280;
    } else if (id == 0x60) {
        type_ = BmpType::BME280;
    } else {
        close_device();
        return false;
    }
    if (!init()) {
        close_device();
        return false;
    }
    return true;
}

void BmpSensor::close_device() {
    if (fd_ >= 0) ::close(fd_);
    fd_ = -1;
    dev_name_.clear();
    type_ = BmpType::None;
}

std::string BmpSensor::type_name() const {
    switch (type_) {
        case BmpType::BMP180: return "BMP180";
        case BmpType::BMP280: return "BMP280";
        case BmpType::BME280: return "BME280";
        default: return "None";
    }
}

bool BmpSensor::write_reg(uint8_t reg, uint8_t val) {
    if (!set_slave()) return false;
    uint8_t data[2] = {reg, val};
    return ::write(fd_, data, 2) == 2;
}

bool BmpSensor::read_regs(uint8_t reg, uint8_t *buf, int len) {
    if (!set_slave()) return false;
    if (::write(fd_, &reg, 1) != 1) return false;
    return ::read(fd_, buf, len) == len;
}

bool BmpSensor::read_reg(uint8_t reg, uint8_t &val) { return read_regs(reg, &val, 1); }

bool BmpSensor::init() {
    if (type_ == BmpType::BMP180) return init_bmp180();
    if (type_ == BmpType::BMP280 || type_ == BmpType::BME280) return init_bmp280();
    return false;
}

bool BmpSensor::read(BmpReading &out) {
    if (type_ == BmpType::BMP180) return read_bmp180(out);
    if (type_ == BmpType::BMP280 || type_ == BmpType::BME280) return read_bmp280(out);
    return false;
}

bool BmpSensor::read_calib_bmp280() {
    uint8_t c[24]{};
    if (!read_regs(0x88, c, 24)) return false;
    dig_T1_ = le_u16(&c[0]);
    dig_T2_ = le_s16(&c[2]);
    dig_T3_ = le_s16(&c[4]);
    dig_P1_ = le_u16(&c[6]);
    dig_P2_ = le_s16(&c[8]);
    dig_P3_ = le_s16(&c[10]);
    dig_P4_ = le_s16(&c[12]);
    dig_P5_ = le_s16(&c[14]);
    dig_P6_ = le_s16(&c[16]);
    dig_P7_ = le_s16(&c[18]);
    dig_P8_ = le_s16(&c[20]);
    dig_P9_ = le_s16(&c[22]);
    return dig_T1_ != 0 && dig_P1_ != 0;
}

bool BmpSensor::init_bmp280() {
    if (!read_calib_bmp280()) return false;
    // osrs_t x1, osrs_p x1, normal mode
    bool ok = true;
    ok &= write_reg(0xF5, 0xA0); // standby 1000ms, filter off
    ok &= write_reg(0xF4, 0x27); // temp x1, pressure x1, normal
    sleep_us(10000);
    return ok;
}

bool BmpSensor::read_bmp280(BmpReading &out) {
    uint8_t b[6]{};
    if (!read_regs(0xF7, b, 6)) return false;
    int32_t adc_P = (static_cast<int32_t>(b[0]) << 12) | (static_cast<int32_t>(b[1]) << 4) | (b[2] >> 4);
    int32_t adc_T = (static_cast<int32_t>(b[3]) << 12) | (static_cast<int32_t>(b[4]) << 4) | (b[5] >> 4);

    int32_t var1 = ((((adc_T >> 3) - (static_cast<int32_t>(dig_T1_) << 1))) * static_cast<int32_t>(dig_T2_)) >> 11;
    int32_t var2 = (((((adc_T >> 4) - static_cast<int32_t>(dig_T1_)) * ((adc_T >> 4) - static_cast<int32_t>(dig_T1_))) >> 12) * static_cast<int32_t>(dig_T3_)) >> 14;
    t_fine_ = var1 + var2;
    float T = static_cast<float>((t_fine_ * 5 + 128) >> 8) / 100.0f;

    int64_t pvar1 = static_cast<int64_t>(t_fine_) - 128000;
    int64_t pvar2 = pvar1 * pvar1 * static_cast<int64_t>(dig_P6_);
    pvar2 += (pvar1 * static_cast<int64_t>(dig_P5_)) << 17;
    pvar2 += static_cast<int64_t>(dig_P4_) << 35;
    pvar1 = ((pvar1 * pvar1 * static_cast<int64_t>(dig_P3_)) >> 8) + ((pvar1 * static_cast<int64_t>(dig_P2_)) << 12);
    pvar1 = (((static_cast<int64_t>(1) << 47) + pvar1)) * static_cast<int64_t>(dig_P1_) >> 33;
    if (pvar1 == 0) return false;
    int64_t p = 1048576 - adc_P;
    p = (((p << 31) - pvar2) * 3125) / pvar1;
    pvar1 = (static_cast<int64_t>(dig_P9_) * (p >> 13) * (p >> 13)) >> 25;
    pvar2 = (static_cast<int64_t>(dig_P8_) * p) >> 19;
    p = ((p + pvar1 + pvar2) >> 8) + (static_cast<int64_t>(dig_P7_) << 4);
    float P = static_cast<float>(p) / 256.0f;

    out.temperature_c = T;
    out.pressure_pa = P;
    out.altitude_m = 44330.0f * (1.0f - std::pow(P / sea_level_pressure_pa_, 0.1903f));
    out.valid = true;
    return true;
}

bool BmpSensor::read_calib_bmp180() {
    uint8_t c[22]{};
    if (!read_regs(0xAA, c, 22)) return false;
    ac1_ = be_s16(&c[0]); ac2_ = be_s16(&c[2]); ac3_ = be_s16(&c[4]); ac4_ = be_u16(&c[6]);
    ac5_ = be_u16(&c[8]); ac6_ = be_u16(&c[10]); b1_ = be_s16(&c[12]); b2_ = be_s16(&c[14]);
    mb_ = be_s16(&c[16]); mc_ = be_s16(&c[18]); md_ = be_s16(&c[20]);
    return ac1_ != 0 && ac4_ != 0 && ac5_ != 0;
}

bool BmpSensor::init_bmp180() {
    return read_calib_bmp180();
}

bool BmpSensor::read_bmp180(BmpReading &out) {
    // BMP180 integer algorithm, OSS=0 for reliability.
    constexpr int OSS = 0;
    uint8_t b[3]{};

    if (!write_reg(0xF4, 0x2E)) return false;
    sleep_us(5000);
    if (!read_regs(0xF6, b, 2)) return false;
    int32_t UT = static_cast<int32_t>(be_u16(b));

    if (!write_reg(0xF4, 0x34 + (OSS << 6))) return false;
    sleep_us(8000);
    if (!read_regs(0xF6, b, 3)) return false;
    int32_t UP = (((static_cast<int32_t>(b[0]) << 16) | (static_cast<int32_t>(b[1]) << 8) | b[2]) >> (8 - OSS));

    int32_t X1 = ((UT - static_cast<int32_t>(ac6_)) * static_cast<int32_t>(ac5_)) >> 15;
    int32_t X2 = (static_cast<int32_t>(mc_) << 11) / (X1 + md_);
    int32_t B5 = X1 + X2;
    float temperature = static_cast<float>((B5 + 8) >> 4) / 10.0f;

    int32_t B6 = B5 - 4000;
    X1 = (static_cast<int32_t>(b2_) * ((B6 * B6) >> 12)) >> 11;
    X2 = (static_cast<int32_t>(ac2_) * B6) >> 11;
    int32_t X3 = X1 + X2;
    int32_t B3 = (((static_cast<int32_t>(ac1_) * 4 + X3) << OSS) + 2) >> 2;
    X1 = (static_cast<int32_t>(ac3_) * B6) >> 13;
    X2 = (static_cast<int32_t>(b1_) * ((B6 * B6) >> 12)) >> 16;
    X3 = ((X1 + X2) + 2) >> 2;
    uint32_t B4 = (static_cast<uint32_t>(ac4_) * static_cast<uint32_t>(X3 + 32768)) >> 15;
    uint32_t B7 = static_cast<uint32_t>(UP - B3) * (50000 >> OSS);
    int32_t p = 0;
    if (B7 < 0x80000000) p = (B7 * 2) / B4;
    else p = (B7 / B4) * 2;
    X1 = (p >> 8) * (p >> 8);
    X1 = (X1 * 3038) >> 16;
    X2 = (-7357 * p) >> 16;
    p = p + ((X1 + X2 + 3791) >> 4);

    out.temperature_c = temperature;
    out.pressure_pa = static_cast<float>(p);
    out.altitude_m = 44330.0f * (1.0f - std::pow(out.pressure_pa / sea_level_pressure_pa_, 0.1903f));
    out.valid = true;
    return true;
}

} // namespace drone

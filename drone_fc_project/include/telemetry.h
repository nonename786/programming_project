#pragma once

#include <array>
#include <cstdint>
#include <string>
#include <vector>

#include "battery.h"
#include "bmp_sensor.h"
#include "esc_pwm.h"
#include "mpu6050.h"
#include "rc_ibus.h"

namespace drone {

struct TelemetryData {
    uint64_t time_ms = 0;
    Attitude att;
    ImuScaled imu;
    BmpReading bmp;
    BatteryState bat;
    RcState rc;
    MotorOutputs motors;
    bool armed = false;
    bool rc_ok = false;
    bool imu_ok = false;
    std::string mode;
    std::string status;
};

class Telemetry {
public:
    Telemetry();
    ~Telemetry();

    bool open_bluetooth_first(const std::vector<std::string> &ports, int baud);
    bool open_bluetooth(const std::string &port, int baud);
    void close_bluetooth();
    void set_log_file(const std::string &path);
    void set_stdout_enabled(bool enabled) { stdout_enabled_ = enabled; }
    const std::string &bt_port() const { return bt_port_; }
    bool bt_open() const { return bt_fd_ >= 0; }

    void send(const TelemetryData &d);
    void send_text(const std::string &line);

private:
    bool configure_serial(int fd, int baud);
    std::string make_csv_header() const;
    std::string make_csv_line(const TelemetryData &d) const;

    int bt_fd_ = -1;
    std::string bt_port_;
    std::string log_path_;
    bool wrote_header_ = false;
    bool stdout_enabled_ = true;
};

} // namespace drone

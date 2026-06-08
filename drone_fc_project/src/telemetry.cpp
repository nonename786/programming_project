#include "telemetry.h"

#include "common.h"
#include "config.h"

#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <termios.h>
#include <unistd.h>

namespace drone {

static speed_t baud_to_speed(int baud) {
    switch (baud) {
        case 9600: return B9600;
        case 19200: return B19200;
        case 38400: return B38400;
        case 57600: return B57600;
        case 115200: return B115200;
        case 230400: return B230400;
        default: return B115200;
    }
}

Telemetry::Telemetry() = default;
Telemetry::~Telemetry() { close_bluetooth(); }

bool Telemetry::configure_serial(int fd, int baud) {
    termios tio{};
    if (tcgetattr(fd, &tio) != 0) return false;
    cfmakeraw(&tio);
    cfsetispeed(&tio, baud_to_speed(baud));
    cfsetospeed(&tio, baud_to_speed(baud));
    tio.c_cflag |= CLOCAL | CREAD;
    tio.c_cflag &= ~PARENB;
    tio.c_cflag &= ~CSTOPB;
    tio.c_cflag &= ~CSIZE;
    tio.c_cflag |= CS8;
    tio.c_cflag &= ~CRTSCTS;
    tio.c_cc[VMIN] = 0;
    tio.c_cc[VTIME] = 0;
    tcflush(fd, TCIOFLUSH);
    return tcsetattr(fd, TCSANOW, &tio) == 0;
}

bool Telemetry::open_bluetooth_first(const std::vector<std::string> &ports, int baud) {
    for (const auto &p : ports) {
        if (open_bluetooth(p, baud)) return true;
    }
    return false;
}

bool Telemetry::open_bluetooth(const std::string &port, int baud) {
    close_bluetooth();
    int fd = ::open(port.c_str(), O_RDWR | O_NOCTTY | O_NONBLOCK);
    if (fd < 0) return false;
    if (!configure_serial(fd, baud)) {
        ::close(fd);
        return false;
    }
    bt_fd_ = fd;
    bt_port_ = port;
    return true;
}

void Telemetry::close_bluetooth() {
    if (bt_fd_ >= 0) ::close(bt_fd_);
    bt_fd_ = -1;
    bt_port_.clear();
}

void Telemetry::set_log_file(const std::string &path) {
    log_path_ = path;
    wrote_header_ = false;
}

std::string Telemetry::make_csv_header() const {
    return "time_ms,mode,armed,rc_ok,imu_ok,roll,pitch,yaw,gx,gy,gz,temp_c,pressure_pa,altitude_m,battery_v,adc_raw,ch1,ch2,ch3,ch4,ch5,ch6,m1,m2,m3,m4,status\r\n";
}

std::string Telemetry::make_csv_line(const TelemetryData &d) const {
    auto ch = [&](int i) -> int {
        if (!d.rc.valid) return 0;
        return d.rc.ch[static_cast<size_t>(i)];
    };
    std::ostringstream ss;
    ss.setf(std::ios::fixed);
    ss << std::setprecision(2);
    ss << d.time_ms << ','
       << d.mode << ','
       << (d.armed ? 1 : 0) << ','
       << (d.rc_ok ? 1 : 0) << ','
       << (d.imu_ok ? 1 : 0) << ','
       << d.att.roll_deg << ',' << d.att.pitch_deg << ',' << d.att.yaw_deg << ','
       << d.imu.gx_dps << ',' << d.imu.gy_dps << ',' << d.imu.gz_dps << ','
       << d.bmp.temperature_c << ',' << d.bmp.pressure_pa << ',' << d.bmp.altitude_m << ','
       << d.bat.battery_voltage << ',' << d.bat.raw << ','
       << ch(0) << ',' << ch(1) << ',' << ch(2) << ',' << ch(3) << ',' << ch(4) << ',' << ch(5) << ','
       << d.motors.m1 << ',' << d.motors.m2 << ',' << d.motors.m3 << ',' << d.motors.m4 << ','
       << d.status << "\r\n";
    return ss.str();
}

void Telemetry::send_text(const std::string &line) {
    std::string s = line;
    if (s.size() < 2 || s.substr(s.size() - 2) != "\r\n") s += "\r\n";
    if (bt_fd_ >= 0) {
        (void)::write(bt_fd_, s.data(), s.size());
    }
    if (!log_path_.empty()) {
        std::ofstream f(log_path_, std::ios::app);
        if (f) f << s;
    }
    if (stdout_enabled_) {
        std::cout << s;
        std::cout.flush();
    }
}

void Telemetry::send(const TelemetryData &d) {
    if (!wrote_header_) {
        std::string h = make_csv_header();
        if (bt_fd_ >= 0) (void)::write(bt_fd_, h.data(), h.size());
        if (!log_path_.empty()) {
            std::ofstream f(log_path_, std::ios::app);
            if (f) f << h;
        }
        if (stdout_enabled_) std::cout << h;
        wrote_header_ = true;
    }
    std::string line = make_csv_line(d);
    if (bt_fd_ >= 0) (void)::write(bt_fd_, line.data(), line.size());
    if (!log_path_.empty()) {
        std::ofstream f(log_path_, std::ios::app);
        if (f) f << line;
    }
    if (stdout_enabled_) {
        std::cout << line;
        std::cout.flush();
    }
}

} // namespace drone

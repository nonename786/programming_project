#include "rc_ibus.h"

#include "common.h"
#include "config.h"

#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <iostream>
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

static bool configure_serial(int fd, int baud) {
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

IBusReceiver::IBusReceiver() = default;

IBusReceiver::~IBusReceiver() { close_port(); }

bool IBusReceiver::open_first(const std::vector<std::string> &ports, int baud) {
    for (const auto &p : ports) {
        if (open_port(p, baud)) return true;
    }
    return false;
}

bool IBusReceiver::open_port(const std::string &port, int baud) {
    close_port();
    int fd = ::open(port.c_str(), O_RDONLY | O_NOCTTY | O_NONBLOCK);
    if (fd < 0) {
        return false;
    }
    if (!configure_serial(fd, baud)) {
        ::close(fd);
        return false;
    }
    fd_ = fd;
    port_name_ = port;
    buffer_.clear();
    return true;
}

void IBusReceiver::close_port() {
    if (fd_ >= 0) ::close(fd_);
    fd_ = -1;
    port_name_.clear();
    buffer_.clear();
}

bool IBusReceiver::parse_frame(const uint8_t f[32], std::array<uint16_t, 14> &channels) {
    if (f[0] != 0x20 || f[1] != 0x40) return false;
    uint16_t checksum = 0xFFFF;
    for (int i = 0; i < 30; ++i) checksum -= f[i];
    uint16_t rx_checksum = static_cast<uint16_t>(f[30]) |
                           (static_cast<uint16_t>(f[31]) << 8);
    if (checksum != rx_checksum) return false;

    for (int i = 0; i < 14; ++i) {
        channels[i] = static_cast<uint16_t>(f[2 + i * 2]) |
                      (static_cast<uint16_t>(f[3 + i * 2]) << 8);
    }
    return true;
}

bool IBusReceiver::poll(RcState &state) {
    if (fd_ < 0) return false;

    uint8_t tmp[128];
    bool got_new_frame = false;
    while (true) {
        ssize_t n = ::read(fd_, tmp, sizeof(tmp));
        if (n > 0) {
            buffer_.insert(buffer_.end(), tmp, tmp + n);
            if (buffer_.size() > 256) {
                buffer_.erase(buffer_.begin(), buffer_.end() - 128);
            }
        } else {
            if (n < 0 && errno != EAGAIN && errno != EWOULDBLOCK) {
                std::cerr << "IBUS read error on " << port_name_ << ": " << std::strerror(errno) << "\n";
            }
            break;
        }
    }

    while (buffer_.size() >= IBUS_FRAME_SIZE) {
        // 对齐帧头。
        size_t header = 0;
        while (header + 1 < buffer_.size() && !(buffer_[header] == 0x20 && buffer_[header + 1] == 0x40)) {
            ++header;
        }
        if (header > 0) buffer_.erase(buffer_.begin(), buffer_.begin() + static_cast<long>(header));
        if (buffer_.size() < IBUS_FRAME_SIZE) break;

        std::array<uint16_t, 14> channels{};
        if (parse_frame(buffer_.data(), channels)) {
            state.ch = channels;
            state.last_frame_ms = now_ms();
            state.valid = true;
            got_new_frame = true;
            buffer_.erase(buffer_.begin(), buffer_.begin() + IBUS_FRAME_SIZE);
        } else {
            buffer_.erase(buffer_.begin());
        }
    }

    return got_new_frame;
}

} // namespace drone

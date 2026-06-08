#pragma once

#include <array>
#include <cstdint>
#include <string>
#include <vector>

namespace drone {

struct RcState {
    std::array<uint16_t, 14> ch{};
    uint64_t last_frame_ms = 0;
    bool valid = false;
};

class IBusReceiver {
public:
    IBusReceiver();
    ~IBusReceiver();

    bool open_first(const std::vector<std::string> &ports, int baud);
    bool open_port(const std::string &port, int baud);
    void close_port();
    bool is_open() const { return fd_ >= 0; }
    const std::string &port_name() const { return port_name_; }

    // 非阻塞读取串口，解析最新一帧。返回本次调用是否收到新有效帧。
    bool poll(RcState &state);
    static bool parse_frame(const uint8_t f[32], std::array<uint16_t, 14> &channels);

private:
    int fd_ = -1;
    std::string port_name_;
    std::vector<uint8_t> buffer_;
};

} // namespace drone

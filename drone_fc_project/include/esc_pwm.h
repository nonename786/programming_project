#pragma once

#include <array>
#include <string>

namespace drone {

struct MotorOutputs {
    int m1 = 1000;
    int m2 = 1000;
    int m3 = 1000;
    int m4 = 1000;
};

struct PwmChannelConfig {
    std::string chip;
    int channel = 0;
    std::string name;
};

class EscPwm {
public:
    explicit EscPwm(bool dry_run = false);
    bool init(int period_us = 20000);
    bool write_us(const MotorOutputs &out);
    bool write_all_us(int pulse_us);
    bool stop_all();
    std::string status() const;

private:
    bool export_channel(const PwmChannelConfig &cfg);
    std::string pwm_path(const PwmChannelConfig &cfg) const;
    bool set_one_us(const PwmChannelConfig &cfg, int pulse_us);

    std::array<PwmChannelConfig, 4> channels_;
    bool dry_run_ = false;
    int period_us_ = 20000;
};

} // namespace drone

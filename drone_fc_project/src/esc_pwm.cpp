#include "esc_pwm.h"

#include "common.h"
#include "config.h"

#include <cstdio>
#include <iostream>
#include <sstream>

namespace drone {

EscPwm::EscPwm(bool dry_run) : dry_run_(dry_run) {
    channels_ = {{
        {M1_PWM_CHIP, M1_PWM_CHANNEL, "M1_left_front_GP6_PWM9"},
        {M2_PWM_CHIP, M2_PWM_CHANNEL, "M2_right_front_GP7_PWM8"},
        {M3_PWM_CHIP, M3_PWM_CHANNEL, "M3_left_rear_GP8_PWM7"},
        {M4_PWM_CHIP, M4_PWM_CHANNEL, "M4_right_rear_GP9_PWM4"},
    }};
}

std::string EscPwm::pwm_path(const PwmChannelConfig &cfg) const {
    return cfg.chip + "/pwm" + std::to_string(cfg.channel);
}

bool EscPwm::export_channel(const PwmChannelConfig &cfg) {
    if (dry_run_) return true;
    if (!file_exists(cfg.chip)) {
        std::cerr << "PWM chip not found: " << cfg.chip << " for " << cfg.name << "\n";
        return false;
    }
    std::string p = pwm_path(cfg);
    if (!file_exists(p)) {
        if (!write_text_file(cfg.chip + "/export", std::to_string(cfg.channel))) {
            // 如果已经 export 或内核忙，短暂等待后再检查。
            sleep_us(100000);
            if (!file_exists(p)) {
                std::cerr << "Failed to export PWM " << cfg.name << " at " << cfg.chip
                          << " channel " << cfg.channel << "\n";
                return false;
            }
        }
        sleep_us(100000);
    }
    return file_exists(p);
}

bool EscPwm::init(int period_us) {
    period_us_ = period_us;
    bool ok = true;
    for (const auto &cfg : channels_) {
        if (!export_channel(cfg)) {
            ok = false;
            continue;
        }
        if (!dry_run_) {
            std::string p = pwm_path(cfg);
            write_text_file(p + "/enable", "0");
            // sysfs PWM 单位为纳秒。
            if (!write_text_file(p + "/period", std::to_string(period_us_ * 1000))) {
                std::cerr << "Failed to set PWM period for " << cfg.name << "\n";
                ok = false;
            }
            if (!write_text_file(p + "/duty_cycle", std::to_string(PWM_STOP_US * 1000))) {
                std::cerr << "Failed to set PWM initial duty for " << cfg.name << "\n";
                ok = false;
            }
            if (!write_text_file(p + "/enable", "1")) {
                std::cerr << "Failed to enable PWM for " << cfg.name << "\n";
                ok = false;
            }
        }
    }
    stop_all();
    return ok;
}

bool EscPwm::set_one_us(const PwmChannelConfig &cfg, int pulse_us) {
    pulse_us = clamp_int(pulse_us, PWM_MIN_US, 2000);
    if (dry_run_) return true;
    std::string p = pwm_path(cfg);
    return write_text_file(p + "/duty_cycle", std::to_string(pulse_us * 1000));
}

bool EscPwm::write_us(const MotorOutputs &out) {
    bool ok = true;
    ok &= set_one_us(channels_[0], out.m1);
    ok &= set_one_us(channels_[1], out.m2);
    ok &= set_one_us(channels_[2], out.m3);
    ok &= set_one_us(channels_[3], out.m4);
    return ok;
}

bool EscPwm::write_all_us(int pulse_us) {
    return write_us({pulse_us, pulse_us, pulse_us, pulse_us});
}

bool EscPwm::stop_all() {
    return write_all_us(PWM_STOP_US);
}

std::string EscPwm::status() const {
    std::ostringstream ss;
    ss << "PWM: "
       << channels_[0].name << "=" << channels_[0].chip << "/pwm" << channels_[0].channel << ", "
       << channels_[1].name << "=" << channels_[1].chip << "/pwm" << channels_[1].channel << ", "
       << channels_[2].name << "=" << channels_[2].chip << "/pwm" << channels_[2].channel << ", "
       << channels_[3].name << "=" << channels_[3].chip << "/pwm" << channels_[3].channel;
    if (dry_run_) ss << " [DRY-RUN]";
    return ss.str();
}

} // namespace drone

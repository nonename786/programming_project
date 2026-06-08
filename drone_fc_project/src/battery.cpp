#include "battery.h"

#include "common.h"
#include "config.h"

#include <iostream>

namespace drone {

BatteryMonitor::BatteryMonitor() = default;

bool BatteryMonitor::init(const std::string &adc_path, float ref_v, float adc_max_raw, float battery_scale) {
    adc_path_ = adc_path;
    ref_v_ = ref_v;
    adc_max_raw_ = adc_max_raw;
    battery_scale_ = battery_scale;
    has_filter_ = false;
    filtered_v_ = 0;
    return !adc_path_.empty() && file_exists(adc_path_);
}

std::string BatteryMonitor::find_adc_path() const {
    std::vector<std::string> candidates;
    for (int dev = 0; dev < 4; ++dev) {
        for (int ch = 0; ch < 8; ++ch) {
            candidates.push_back("/sys/bus/iio/devices/iio:device" + std::to_string(dev) +
                                 "/in_voltage" + std::to_string(ch) + "_raw");
        }
    }
    // GP26/ADC1 优先。
    for (const auto &p : candidates) {
        if (p.find("in_voltage1_raw") != std::string::npos && file_exists(p)) return p;
    }
    for (const auto &p : candidates) {
        if (file_exists(p)) return p;
    }
    return "";
}

bool BatteryMonitor::init_auto(float ref_v, float adc_max_raw, float battery_scale) {
    return init(find_adc_path(), ref_v, adc_max_raw, battery_scale);
}

bool BatteryMonitor::read(BatteryState &out) {
    out = BatteryState{};
    if (adc_path_.empty()) return false;
    int raw = -1;
    if (!read_int_file(adc_path_, raw) || raw < 0) return false;
    float adc_v = static_cast<float>(raw) / adc_max_raw_ * ref_v_;
    float bat_v = adc_v * battery_scale_;
    if (!has_filter_) {
        filtered_v_ = bat_v;
        has_filter_ = true;
    } else {
        filtered_v_ = filtered_v_ * 0.85f + bat_v * 0.15f;
    }

    out.raw = raw;
    out.adc_voltage = adc_v;
    out.battery_voltage = filtered_v_;
    out.valid = true;
    out.warn = out.battery_voltage > 1.0f && out.battery_voltage < BAT_WARN_V;
    out.limit = out.battery_voltage > 1.0f && out.battery_voltage < BAT_LIMIT_V;
    out.critical = out.battery_voltage > 1.0f && out.battery_voltage < BAT_CRITICAL_V;
    return true;
}

} // namespace drone

#pragma once

#include <string>

namespace drone {

struct BatteryState {
    float adc_voltage = 0;
    float battery_voltage = 0;
    int raw = -1;
    bool valid = false;
    bool warn = false;
    bool limit = false;
    bool critical = false;
};

class BatteryMonitor {
public:
    BatteryMonitor();
    bool init(const std::string &adc_path, float ref_v, float adc_max_raw, float battery_scale);
    bool init_auto(float ref_v, float adc_max_raw, float battery_scale);
    bool read(BatteryState &out);
    const std::string &path() const { return adc_path_; }

private:
    std::string find_adc_path() const;

    std::string adc_path_;
    float ref_v_ = 1.8f;
    float adc_max_raw_ = 4095.0f;
    float battery_scale_ = 7.5f;
    float filtered_v_ = 0;
    bool has_filter_ = false;
};

} // namespace drone

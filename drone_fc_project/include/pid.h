#pragma once

#include "common.h"

namespace drone {

class PID {
public:
    PID() = default;
    PID(float kp, float ki, float kd, float integral_limit, float output_limit)
        : kp_(kp), ki_(ki), kd_(kd), integral_limit_(integral_limit), output_limit_(output_limit) {}

    void set(float kp, float ki, float kd, float integral_limit, float output_limit) {
        kp_ = kp; ki_ = ki; kd_ = kd; integral_limit_ = integral_limit; output_limit_ = output_limit;
    }

    float update(float target, float measured, float dt_s) {
        if (dt_s <= 0.0f || dt_s > 0.1f) dt_s = 0.01f;
        float error = target - measured;
        integral_ += error * dt_s;
        integral_ = clamp_float(integral_, -integral_limit_, integral_limit_);
        float derivative = first_ ? 0.0f : (error - last_error_) / dt_s;
        last_error_ = error;
        first_ = false;
        float out = kp_ * error + ki_ * integral_ + kd_ * derivative;
        return clamp_float(out, -output_limit_, output_limit_);
    }

    void reset() {
        integral_ = 0.0f;
        last_error_ = 0.0f;
        first_ = true;
    }

private:
    float kp_ = 0, ki_ = 0, kd_ = 0;
    float integral_ = 0;
    float last_error_ = 0;
    float integral_limit_ = 100;
    float output_limit_ = 250;
    bool first_ = true;
};

} // namespace drone

#include "common.h"

#include <algorithm>
#include <chrono>
#include <cctype>
#include <cerrno>
#include <cmath>
#include <cstring>
#include <fstream>
#include <iostream>
#include <sstream>
#include <thread>
#include <unistd.h>

namespace drone {

uint64_t now_us() {
    using namespace std::chrono;
    return duration_cast<microseconds>(steady_clock::now().time_since_epoch()).count();
}

uint64_t now_ms() { return now_us() / 1000ULL; }

void sleep_us(uint64_t us) {
    std::this_thread::sleep_for(std::chrono::microseconds(us));
}

void sleep_until_us(uint64_t target_us) {
    uint64_t t = now_us();
    if (target_us > t) sleep_us(target_us - t);
}

bool file_exists(const std::string &path) {
    return access(path.c_str(), F_OK) == 0;
}

bool write_text_file(const std::string &path, const std::string &value) {
    std::ofstream f(path);
    if (!f) return false;
    f << value;
    return static_cast<bool>(f);
}

bool read_text_file(const std::string &path, std::string &out) {
    std::ifstream f(path);
    if (!f) return false;
    std::ostringstream ss;
    ss << f.rdbuf();
    out = ss.str();
    return true;
}

bool read_int_file(const std::string &path, int &out) {
    std::ifstream f(path);
    if (!f) return false;
    f >> out;
    return !f.fail();
}

bool read_float_file(const std::string &path, float &out) {
    std::ifstream f(path);
    if (!f) return false;
    f >> out;
    return !f.fail();
}

std::string trim(const std::string &s) {
    size_t a = 0;
    while (a < s.size() && std::isspace(static_cast<unsigned char>(s[a]))) ++a;
    size_t b = s.size();
    while (b > a && std::isspace(static_cast<unsigned char>(s[b - 1]))) --b;
    return s.substr(a, b - a);
}

std::string getenv_str(const char *name, const std::string &fallback) {
    const char *v = std::getenv(name);
    if (!v || !*v) return fallback;
    return std::string(v);
}

int getenv_int(const char *name, int fallback) {
    const char *v = std::getenv(name);
    if (!v || !*v) return fallback;
    char *end = nullptr;
    long n = std::strtol(v, &end, 10);
    if (end == v) return fallback;
    return static_cast<int>(n);
}

float getenv_float(const char *name, float fallback) {
    const char *v = std::getenv(name);
    if (!v || !*v) return fallback;
    char *end = nullptr;
    float n = std::strtof(v, &end);
    if (end == v) return fallback;
    return n;
}

bool getenv_bool(const char *name, bool fallback) {
    const char *v = std::getenv(name);
    if (!v || !*v) return fallback;
    std::string s = v;
    std::transform(s.begin(), s.end(), s.begin(), [](unsigned char c){ return std::tolower(c); });
    if (s == "1" || s == "true" || s == "yes" || s == "on") return true;
    if (s == "0" || s == "false" || s == "no" || s == "off") return false;
    return fallback;
}

std::vector<std::string> split_csv_env(const char *name, const std::vector<std::string> &fallback) {
    std::string s = getenv_str(name, "");
    if (s.empty()) return fallback;
    std::vector<std::string> out;
    std::stringstream ss(s);
    std::string item;
    while (std::getline(ss, item, ',')) {
        item = trim(item);
        if (!item.empty()) out.push_back(item);
    }
    return out.empty() ? fallback : out;
}

int clamp_int(int v, int lo, int hi) {
    return std::max(lo, std::min(hi, v));
}

float clamp_float(float v, float lo, float hi) {
    return std::max(lo, std::min(hi, v));
}

float map_float(float v, float in_min, float in_max, float out_min, float out_max) {
    if (std::fabs(in_max - in_min) < 1e-6f) return out_min;
    float t = (v - in_min) / (in_max - in_min);
    return out_min + t * (out_max - out_min);
}

float apply_deadband(float v, float deadband) {
    return (std::fabs(v) < deadband) ? 0.0f : v;
}

} // namespace drone

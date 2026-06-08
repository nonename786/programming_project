#pragma once

#include <array>
#include <cstdint>
#include <cstdlib>
#include <string>
#include <vector>

namespace drone {

uint64_t now_us();
uint64_t now_ms();
void sleep_us(uint64_t us);
void sleep_until_us(uint64_t target_us);

bool file_exists(const std::string &path);
bool write_text_file(const std::string &path, const std::string &value);
bool read_text_file(const std::string &path, std::string &out);
bool read_int_file(const std::string &path, int &out);
bool read_float_file(const std::string &path, float &out);
std::string trim(const std::string &s);

std::string getenv_str(const char *name, const std::string &fallback);
int getenv_int(const char *name, int fallback);
float getenv_float(const char *name, float fallback);
bool getenv_bool(const char *name, bool fallback);

std::vector<std::string> split_csv_env(const char *name, const std::vector<std::string> &fallback);

int clamp_int(int v, int lo, int hi);
float clamp_float(float v, float lo, float hi);
float map_float(float v, float in_min, float in_max, float out_min, float out_max);
float apply_deadband(float v, float deadband);

} // namespace drone

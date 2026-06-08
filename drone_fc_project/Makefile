TARGET := drone_fc

SRC_DIR := src
INC_DIR := include
BUILD_DIR := build

SRCS := $(wildcard $(SRC_DIR)/*.cpp)
OBJS := $(patsubst $(SRC_DIR)/%.cpp,$(BUILD_DIR)/%.o,$(SRCS))

# 兼容 Milk-V duo-examples/envsetup.sh，也兼容本机 g++ 语法检查。
ifneq ($(TOOLCHAIN_PREFIX),)
CXX := $(TOOLCHAIN_PREFIX)g++
else ifneq ($(CROSS_COMPILE),)
CXX := $(CROSS_COMPILE)g++
else
CXX ?= g++
endif

CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra -I$(INC_DIR)
LDFLAGS ?=
LDLIBS := -lm

.PHONY: all clean install

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LDFLAGS) $(LDLIBS)

$(BUILD_DIR)/%.o: $(SRC_DIR)/%.cpp | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) -c $< -o $@

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

clean:
	rm -rf $(BUILD_DIR) $(TARGET)

install: $(TARGET)
	install -m 0755 $(TARGET) /root/drone_fc
	install -m 0755 scripts/start_drone.sh /root/start_drone.sh
	install -m 0644 config/drone_fc.env /root/drone_fc.env
	install -m 0755 scripts/S99drone /etc/init.d/S99drone

CC ?= clang
OBJC ?= clang

BUILD_DIR := build
BIN := $(BUILD_DIR)/chessnut-ble
TEST_BIN := $(BUILD_DIR)/test_protocol
APP := $(BUILD_DIR)/ChessnutBLE.app
APP_BIN := $(APP)/Contents/MacOS/ChessnutBLE

WARN := -Wall -Wextra -Wpedantic -Werror
CFLAGS := -std=c11 $(WARN) -Iinclude -MMD -MP
OBJCFLAGS := -fobjc-arc $(WARN) -Iinclude -MMD -MP
LDFLAGS := -framework Foundation -framework CoreBluetooth \
	-Wl,-sectcreate,__TEXT,__info_plist,resources/Info.plist

LIB_C_SRCS := src/chessnut_protocol.c
LIB_OBJC_SRCS := src/chessnut_ble_corebluetooth.m
CLI_SRCS := src/chessnut_ble_cli.c
TEST_SRCS := tests/test_protocol.c

LIB_C_OBJS := $(patsubst %.c,$(BUILD_DIR)/%.o,$(LIB_C_SRCS))
LIB_OBJC_OBJS := $(patsubst %.m,$(BUILD_DIR)/%.o,$(LIB_OBJC_SRCS))
CLI_OBJS := $(patsubst %.c,$(BUILD_DIR)/%.o,$(CLI_SRCS))
TEST_OBJS := $(patsubst %.c,$(BUILD_DIR)/%.o,$(TEST_SRCS))

.PHONY: all app clean test scan watch probe smoke

all: $(BIN) app

$(BIN): $(LIB_C_OBJS) $(LIB_OBJC_OBJS) $(CLI_OBJS)
	@mkdir -p $(@D)
	$(CC) $^ $(LDFLAGS) -o $@

app: $(APP_BIN)

$(APP_BIN): $(BIN) resources/AppInfo.plist
	@mkdir -p $(APP)/Contents/MacOS
	cp resources/AppInfo.plist $(APP)/Contents/Info.plist
	cp $(BIN) $(APP_BIN)
	codesign --force --sign - $(APP) >/dev/null

$(TEST_BIN): $(LIB_C_OBJS) $(TEST_OBJS)
	@mkdir -p $(@D)
	$(CC) $^ -o $@

$(BUILD_DIR)/%.o: %.c
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/%.o: %.m
	@mkdir -p $(@D)
	$(OBJC) $(OBJCFLAGS) -c $< -o $@

test: $(TEST_BIN)
	$(TEST_BIN)

scan: $(BIN)
	$(BIN) scan --timeout 8

watch: $(BIN)
	$(BIN) watch --boards 1 --timeout 20

probe: $(BIN)
	$(BIN) probe --boards 1 --timeout 20 --verbose

smoke: test $(BIN)
	$(BIN) scan --timeout 8

clean:
	rm -rf $(BUILD_DIR)

-include $(LIB_C_OBJS:.o=.d)
-include $(LIB_OBJC_OBJS:.o=.d)
-include $(CLI_OBJS:.o=.d)
-include $(TEST_OBJS:.o=.d)

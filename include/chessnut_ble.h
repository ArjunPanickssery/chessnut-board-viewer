#ifndef CHESSNUT_BLE_H
#define CHESSNUT_BLE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "chessnut_protocol.h"

#ifdef __cplusplus
extern "C" {
#endif

#define CHESSNUT_BLE_NAME_MAX 128
#define CHESSNUT_BLE_ID_MAX 128

typedef struct chessnut_ble_options {
  int timeout_seconds;
  int max_boards;
  bool verbose;
  bool include_all_devices;
  const char *name_filter;
} chessnut_ble_options;

typedef struct chessnut_ble_device {
  char name[CHESSNUT_BLE_NAME_MAX];
  char identifier[CHESSNUT_BLE_ID_MAX];
  int rssi;
  bool looks_like_chessnut;
} chessnut_ble_device;

typedef struct chessnut_ble_event {
  int board_index;
  char name[CHESSNUT_BLE_NAME_MAX];
  char identifier[CHESSNUT_BLE_ID_MAX];
  char fen[CHESSNUT_FEN_MAX];
  uint32_t timestamp_ms;
} chessnut_ble_event;

typedef void (*chessnut_ble_fen_callback)(const chessnut_ble_event *event,
                                          void *user_data);

chessnut_ble_options chessnut_ble_default_options(void);

int chessnut_ble_scan(const chessnut_ble_options *options,
                      chessnut_ble_device *devices,
                      size_t capacity,
                      size_t *device_count,
                      char *error,
                      size_t error_len);

int chessnut_ble_watch(const chessnut_ble_options *options,
                       chessnut_ble_fen_callback callback,
                       void *user_data,
                       char *error,
                       size_t error_len);

int chessnut_ble_flash_leds(const chessnut_ble_options *options,
                            const uint8_t rows[8],
                            int hold_milliseconds,
                            char *error,
                            size_t error_len);

#ifdef __cplusplus
}
#endif

#endif

#ifndef CHESSNUT_PROTOCOL_H
#define CHESSNUT_PROTOCOL_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CHESSNUT_BOARD_STATE_LEN 32
#define CHESSNUT_BLE_BOARD_REPORT_LEN 38
#define CHESSNUT_USB_BOARD_REPORT_LEN 65
#define CHESSNUT_FEN_MAX 96
#define CHESSNUT_LED_COMMAND_LEN 10

extern const uint8_t CHESSNUT_CMD_REALTIME[3];
extern const uint8_t CHESSNUT_CMD_UPLOAD[3];
extern const uint8_t CHESSNUT_CMD_BATTERY[3];
extern const uint8_t CHESSNUT_CMD_READY[3];
extern const uint8_t CHESSNUT_RSP_BLE_HEARTBEAT[3];
extern const uint8_t CHESSNUT_RSP_BLE_CONFIRMATION[3];

typedef enum chessnut_protocol_result {
  CHESSNUT_PROTOCOL_OK = 0,
  CHESSNUT_PROTOCOL_ERR_NULL = -1,
  CHESSNUT_PROTOCOL_ERR_SHORT = -2,
  CHESSNUT_PROTOCOL_ERR_NOT_BOARD_REPORT = -3,
  CHESSNUT_PROTOCOL_ERR_BAD_PIECE = -4,
  CHESSNUT_PROTOCOL_ERR_BUFFER = -5,
  CHESSNUT_PROTOCOL_ERR_BAD_SQUARE = -6
} chessnut_protocol_result;

const char *chessnut_protocol_error(chessnut_protocol_result result);
char chessnut_piece_for_code(uint8_t code);
bool chessnut_is_ble_board_report(const uint8_t *data, size_t len);
bool chessnut_is_usb_board_report(const uint8_t *data, size_t len);

chessnut_protocol_result chessnut_extract_board_state(const uint8_t *data,
                                                       size_t len,
                                                       const uint8_t **state,
                                                       size_t *state_len);

chessnut_protocol_result chessnut_board_state_to_fen(const uint8_t state[CHESSNUT_BOARD_STATE_LEN],
                                                     char *fen,
                                                     size_t fen_len);

chessnut_protocol_result chessnut_report_to_fen(const uint8_t *data,
                                                size_t len,
                                                char *fen,
                                                size_t fen_len);

chessnut_protocol_result chessnut_battery_from_report(const uint8_t *data,
                                                      size_t len,
                                                      int *percent,
                                                      bool *charging);

chessnut_protocol_result chessnut_led_rows_from_square(const char *square,
                                                       uint8_t rows[8]);

chessnut_protocol_result chessnut_led_rows_from_squares(const char *const *squares,
                                                        size_t square_count,
                                                        uint8_t rows[8]);

void chessnut_make_led_command(const uint8_t rows[8],
                               uint8_t out[CHESSNUT_LED_COMMAND_LEN]);

#ifdef __cplusplus
}
#endif

#endif

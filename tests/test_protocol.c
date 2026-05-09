#include "chessnut_protocol.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

static const uint8_t START_STATE[CHESSNUT_BOARD_STATE_LEN] = {
    0x58, 0x23, 0x31, 0x85, 0x44, 0x44, 0x44, 0x44,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x77, 0x77, 0x77, 0x77, 0xa6, 0xc9, 0x9b, 0x6a,
};

static void test_start_fen(void) {
  char fen[CHESSNUT_FEN_MAX];
  assert(chessnut_board_state_to_fen(START_STATE, fen, sizeof(fen)) == CHESSNUT_PROTOCOL_OK);
  assert(strcmp(fen, "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR") == 0);
}

static void test_empty_fen(void) {
  uint8_t state[CHESSNUT_BOARD_STATE_LEN] = {0};
  char fen[CHESSNUT_FEN_MAX];
  assert(chessnut_board_state_to_fen(state, fen, sizeof(fen)) == CHESSNUT_PROTOCOL_OK);
  assert(strcmp(fen, "8/8/8/8/8/8/8/8") == 0);
}

static void test_ble_report(void) {
  uint8_t report[CHESSNUT_BLE_BOARD_REPORT_LEN] = {0};
  report[0] = 0x01;
  report[1] = 0x24;
  memcpy(report + 2, START_STATE, sizeof(START_STATE));
  report[34] = 0x78;
  report[35] = 0x56;
  report[36] = 0x34;
  report[37] = 0x12;

  assert(chessnut_is_ble_board_report(report, sizeof(report)));

  char fen[CHESSNUT_FEN_MAX];
  assert(chessnut_report_to_fen(report, sizeof(report), fen, sizeof(fen)) ==
         CHESSNUT_PROTOCOL_OK);
  assert(strcmp(fen, "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR") == 0);
}

static void test_usb_report(void) {
  uint8_t report[CHESSNUT_USB_BOARD_REPORT_LEN] = {0};
  report[0] = 0x01;
  report[1] = 0x3d;
  memcpy(report + 2, START_STATE, sizeof(START_STATE));

  assert(chessnut_is_usb_board_report(report, sizeof(report)));

  char fen[CHESSNUT_FEN_MAX];
  assert(chessnut_report_to_fen(report, sizeof(report), fen, sizeof(fen)) ==
         CHESSNUT_PROTOCOL_OK);
  assert(strcmp(fen, "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR") == 0);
}

static void test_invalid_piece(void) {
  uint8_t state[CHESSNUT_BOARD_STATE_LEN] = {0};
  state[0] = 0xf0;
  char fen[CHESSNUT_FEN_MAX];
  assert(chessnut_board_state_to_fen(state, fen, sizeof(fen)) ==
         CHESSNUT_PROTOCOL_ERR_BAD_PIECE);
}

static void test_battery(void) {
  uint8_t report[] = {0x2a, 0x01, 87, 1};
  int percent = 0;
  bool charging = false;
  assert(chessnut_battery_from_report(report, sizeof(report), &percent, &charging) ==
         CHESSNUT_PROTOCOL_OK);
  assert(percent == 87);
  assert(charging);
}

static void test_led_command(void) {
  const char *squares[] = {"e2", "e4"};
  uint8_t rows[8];
  uint8_t command[CHESSNUT_LED_COMMAND_LEN];
  const uint8_t expected[] = {0x0a, 0x08, 0x00, 0x00, 0x00, 0x00,
                              0x08, 0x00, 0x08, 0x00};

  assert(chessnut_led_rows_from_squares(squares, 2, rows) == CHESSNUT_PROTOCOL_OK);
  chessnut_make_led_command(rows, command);
  assert(memcmp(command, expected, sizeof(expected)) == 0);
}

static void test_bad_square(void) {
  const char *squares[] = {"i9"};
  uint8_t rows[8];
  assert(chessnut_led_rows_from_squares(squares, 1, rows) ==
         CHESSNUT_PROTOCOL_ERR_BAD_SQUARE);
}

int main(void) {
  test_start_fen();
  test_empty_fen();
  test_ble_report();
  test_usb_report();
  test_invalid_piece();
  test_battery();
  test_led_command();
  test_bad_square();
  printf("protocol tests passed\n");
  return 0;
}

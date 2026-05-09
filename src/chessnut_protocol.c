#include "chessnut_protocol.h"

#include <ctype.h>
#include <stdio.h>
#include <string.h>

const uint8_t CHESSNUT_CMD_REALTIME[3] = {0x21, 0x01, 0x00};
const uint8_t CHESSNUT_CMD_UPLOAD[3] = {0x21, 0x01, 0x01};
const uint8_t CHESSNUT_CMD_BATTERY[3] = {0x29, 0x01, 0x00};
const uint8_t CHESSNUT_CMD_READY[3] = {0x33, 0x01, 0x00};
const uint8_t CHESSNUT_RSP_BLE_HEARTBEAT[3] = {0x23, 0x01, 0x00};
const uint8_t CHESSNUT_RSP_BLE_CONFIRMATION[3] = {0x21, 0x01, 0x00};

static const char PIECES[16] = {
    '0', 'q', 'k', 'b', 'p', 'n', 'R', 'P',
    'r', 'B', 'N', 'Q', 'K', '?', '?', '?',
};

const char *chessnut_protocol_error(chessnut_protocol_result result) {
  switch (result) {
  case CHESSNUT_PROTOCOL_OK:
    return "ok";
  case CHESSNUT_PROTOCOL_ERR_NULL:
    return "null pointer";
  case CHESSNUT_PROTOCOL_ERR_SHORT:
    return "packet too short";
  case CHESSNUT_PROTOCOL_ERR_NOT_BOARD_REPORT:
    return "not a board-state report";
  case CHESSNUT_PROTOCOL_ERR_BAD_PIECE:
    return "invalid piece code";
  case CHESSNUT_PROTOCOL_ERR_BUFFER:
    return "output buffer too small";
  case CHESSNUT_PROTOCOL_ERR_BAD_SQUARE:
    return "invalid square";
  }
  return "unknown protocol error";
}

char chessnut_piece_for_code(uint8_t code) {
  if (code >= sizeof(PIECES)) {
    return '?';
  }
  return PIECES[code];
}

bool chessnut_is_ble_board_report(const uint8_t *data, size_t len) {
  return data != NULL && len >= CHESSNUT_BLE_BOARD_REPORT_LEN && data[0] == 0x01 &&
         data[1] == 0x24;
}

bool chessnut_is_usb_board_report(const uint8_t *data, size_t len) {
  return data != NULL && len >= 34 && data[0] == 0x01 &&
         (data[1] == 0x3d || data[1] == 0x40 || data[1] >= CHESSNUT_BOARD_STATE_LEN);
}

chessnut_protocol_result chessnut_extract_board_state(const uint8_t *data,
                                                       size_t len,
                                                       const uint8_t **state,
                                                       size_t *state_len) {
  if (data == NULL || state == NULL || state_len == NULL) {
    return CHESSNUT_PROTOCOL_ERR_NULL;
  }
  if (len < 34) {
    return CHESSNUT_PROTOCOL_ERR_SHORT;
  }
  if (data[0] != 0x01) {
    return CHESSNUT_PROTOCOL_ERR_NOT_BOARD_REPORT;
  }
  if (data[1] != 0x24 && data[1] != 0x3d && data[1] != 0x40 &&
      data[1] < CHESSNUT_BOARD_STATE_LEN) {
    return CHESSNUT_PROTOCOL_ERR_NOT_BOARD_REPORT;
  }

  *state = data + 2;
  *state_len = CHESSNUT_BOARD_STATE_LEN;
  return CHESSNUT_PROTOCOL_OK;
}

static chessnut_protocol_result append_char(char *fen, size_t fen_len, size_t *pos, char c) {
  if (*pos + 1 >= fen_len) {
    return CHESSNUT_PROTOCOL_ERR_BUFFER;
  }
  fen[(*pos)++] = c;
  fen[*pos] = '\0';
  return CHESSNUT_PROTOCOL_OK;
}

static chessnut_protocol_result append_empty_count(char *fen,
                                                   size_t fen_len,
                                                   size_t *pos,
                                                   int *empty) {
  if (*empty == 0) {
    return CHESSNUT_PROTOCOL_OK;
  }
  chessnut_protocol_result result =
      append_char(fen, fen_len, pos, (char)('0' + *empty));
  *empty = 0;
  return result;
}

static uint8_t piece_code_at_stream_index(const uint8_t state[CHESSNUT_BOARD_STATE_LEN],
                                          int stream_index) {
  uint8_t packed = state[stream_index / 2];
  if (stream_index % 2 == 0) {
    return (uint8_t)(packed & 0x0f);
  }
  return (uint8_t)(packed >> 4);
}

chessnut_protocol_result chessnut_board_state_to_fen(const uint8_t state[CHESSNUT_BOARD_STATE_LEN],
                                                     char *fen,
                                                     size_t fen_len) {
  if (state == NULL || fen == NULL) {
    return CHESSNUT_PROTOCOL_ERR_NULL;
  }
  if (fen_len < CHESSNUT_FEN_MAX) {
    return CHESSNUT_PROTOCOL_ERR_BUFFER;
  }

  size_t pos = 0;
  fen[0] = '\0';

  for (int rank = 0; rank < 8; rank++) {
    int empty = 0;
    for (int file = 0; file < 8; file++) {
      int stream_index = rank * 8 + (7 - file);
      char piece = chessnut_piece_for_code(piece_code_at_stream_index(state, stream_index));
      if (piece == '?') {
        return CHESSNUT_PROTOCOL_ERR_BAD_PIECE;
      }
      if (piece == '0') {
        empty++;
      } else {
        chessnut_protocol_result result =
            append_empty_count(fen, fen_len, &pos, &empty);
        if (result != CHESSNUT_PROTOCOL_OK) {
          return result;
        }
        result = append_char(fen, fen_len, &pos, piece);
        if (result != CHESSNUT_PROTOCOL_OK) {
          return result;
        }
      }
    }
    chessnut_protocol_result result =
        append_empty_count(fen, fen_len, &pos, &empty);
    if (result != CHESSNUT_PROTOCOL_OK) {
      return result;
    }
    if (rank != 7) {
      result = append_char(fen, fen_len, &pos, '/');
      if (result != CHESSNUT_PROTOCOL_OK) {
        return result;
      }
    }
  }

  return CHESSNUT_PROTOCOL_OK;
}

chessnut_protocol_result chessnut_report_to_fen(const uint8_t *data,
                                                size_t len,
                                                char *fen,
                                                size_t fen_len) {
  const uint8_t *state = NULL;
  size_t state_len = 0;
  chessnut_protocol_result result =
      chessnut_extract_board_state(data, len, &state, &state_len);
  if (result != CHESSNUT_PROTOCOL_OK) {
    return result;
  }
  if (state_len != CHESSNUT_BOARD_STATE_LEN) {
    return CHESSNUT_PROTOCOL_ERR_SHORT;
  }
  return chessnut_board_state_to_fen(state, fen, fen_len);
}

chessnut_protocol_result chessnut_battery_from_report(const uint8_t *data,
                                                      size_t len,
                                                      int *percent,
                                                      bool *charging) {
  if (data == NULL || percent == NULL || charging == NULL) {
    return CHESSNUT_PROTOCOL_ERR_NULL;
  }
  if (len < 4) {
    return CHESSNUT_PROTOCOL_ERR_SHORT;
  }
  if (data[0] != 0x2a) {
    return CHESSNUT_PROTOCOL_ERR_NOT_BOARD_REPORT;
  }
  *percent = data[2] > 100 ? 100 : data[2];
  *charging = data[3] == 1;
  return CHESSNUT_PROTOCOL_OK;
}

chessnut_protocol_result chessnut_led_rows_from_square(const char *square,
                                                       uint8_t rows[8]) {
  if (square == NULL || rows == NULL) {
    return CHESSNUT_PROTOCOL_ERR_NULL;
  }
  if (strlen(square) != 2) {
    return CHESSNUT_PROTOCOL_ERR_BAD_SQUARE;
  }

  char file = (char)tolower((unsigned char)square[0]);
  char rank = square[1];
  if (file < 'a' || file > 'h' || rank < '1' || rank > '8') {
    return CHESSNUT_PROTOCOL_ERR_BAD_SQUARE;
  }

  int file_index = file - 'a';
  int rank_number = rank - '0';
  int row_index = 8 - rank_number;
  rows[row_index] |= (uint8_t)(1u << (7 - file_index));
  return CHESSNUT_PROTOCOL_OK;
}

chessnut_protocol_result chessnut_led_rows_from_squares(const char *const *squares,
                                                        size_t square_count,
                                                        uint8_t rows[8]) {
  if (rows == NULL) {
    return CHESSNUT_PROTOCOL_ERR_NULL;
  }
  memset(rows, 0, 8);
  if (squares == NULL && square_count != 0) {
    return CHESSNUT_PROTOCOL_ERR_NULL;
  }
  for (size_t i = 0; i < square_count; i++) {
    chessnut_protocol_result result = chessnut_led_rows_from_square(squares[i], rows);
    if (result != CHESSNUT_PROTOCOL_OK) {
      return result;
    }
  }
  return CHESSNUT_PROTOCOL_OK;
}

void chessnut_make_led_command(const uint8_t rows[8],
                               uint8_t out[CHESSNUT_LED_COMMAND_LEN]) {
  out[0] = 0x0a;
  out[1] = 0x08;
  memcpy(out + 2, rows, 8);
}

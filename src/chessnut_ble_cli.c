#include "chessnut_ble.h"

#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int write_status_file(const char *path, int status) {
  if (path == NULL) {
    return status;
  }
  FILE *file = fopen(path, "w");
  if (file == NULL) {
    return status == 0 ? 1 : status;
  }
  fprintf(file, "%d\n", status);
  fclose(file);
  return status;
}

static int redirect_to_log(const char *path) {
  if (path == NULL) {
    return 0;
  }
  FILE *out = freopen(path, "w", stdout);
  if (out == NULL) {
    return 1;
  }
  FILE *err = freopen(path, "a", stderr);
  if (err == NULL) {
    return 1;
  }
  setvbuf(stdout, NULL, _IOLBF, 0);
  setvbuf(stderr, NULL, _IOLBF, 0);
  return 0;
}

static void usage(FILE *stream) {
  fprintf(stream,
          "Usage:\n"
          "  chessnut-ble [--log FILE] [--status FILE] <command> [options]\n"
          "  chessnut-ble scan [--timeout SEC] [--all] [--name TEXT] [--verbose]\n"
          "  chessnut-ble watch [--boards N] [--timeout SEC] [--name TEXT] [--verbose] [--all-reports]\n"
          "  chessnut-ble probe [--boards N] [--timeout SEC] [--name TEXT] [--verbose]\n"
          "  chessnut-ble led SQUARE... [--timeout SEC] [--hold MS] [--name TEXT] [--verbose]\n"
          "\n"
          "Examples:\n"
          "  chessnut-ble scan --timeout 8\n"
          "  chessnut-ble watch --boards 2 --timeout 30\n"
          "  chessnut-ble led e2 e4 --hold 1500\n");
}

static bool parse_int(const char *value, int *out) {
  char *end = NULL;
  long parsed = strtol(value, &end, 10);
  if (value[0] == '\0' || *end != '\0' || parsed < 0 || parsed > 1000000) {
    return false;
  }
  *out = (int)parsed;
  return true;
}

static int parse_options(int argc,
                         char **argv,
                         int start,
                         chessnut_ble_options *options,
                         int *hold_ms,
                         bool *all_reports,
                         const char ***square_start,
                         size_t *square_count) {
  *options = chessnut_ble_default_options();
  if (hold_ms != NULL) {
    *hold_ms = 1000;
  }
  if (all_reports != NULL) {
    *all_reports = false;
  }
  if (square_start != NULL) {
    *square_start = NULL;
  }
  if (square_count != NULL) {
    *square_count = 0;
  }

  for (int i = start; i < argc; i++) {
    if (strcmp(argv[i], "--timeout") == 0 && i + 1 < argc) {
      if (!parse_int(argv[++i], &options->timeout_seconds)) {
        fprintf(stderr, "Invalid --timeout value\n");
        return 2;
      }
    } else if (strcmp(argv[i], "--boards") == 0 && i + 1 < argc) {
      if (!parse_int(argv[++i], &options->max_boards) || options->max_boards <= 0) {
        fprintf(stderr, "Invalid --boards value\n");
        return 2;
      }
    } else if (strcmp(argv[i], "--name") == 0 && i + 1 < argc) {
      options->name_filter = argv[++i];
    } else if (strcmp(argv[i], "--verbose") == 0) {
      options->verbose = true;
    } else if (strcmp(argv[i], "--all") == 0) {
      options->include_all_devices = true;
    } else if (strcmp(argv[i], "--all-reports") == 0 && all_reports != NULL) {
      *all_reports = true;
    } else if (strcmp(argv[i], "--hold") == 0 && i + 1 < argc && hold_ms != NULL) {
      if (!parse_int(argv[++i], hold_ms)) {
        fprintf(stderr, "Invalid --hold value\n");
        return 2;
      }
    } else if (argv[i][0] == '-') {
      fprintf(stderr, "Unknown option: %s\n", argv[i]);
      return 2;
    } else if (square_start != NULL && square_count != NULL) {
      if (*square_start == NULL) {
        *square_start = (const char **)&argv[i];
      }
      (*square_count)++;
    } else {
      fprintf(stderr, "Unexpected argument: %s\n", argv[i]);
      return 2;
    }
  }
  return 0;
}

typedef struct watch_context {
  bool all_reports;
  char last_fen[8][CHESSNUT_FEN_MAX];
  unsigned long duplicate_count[8];
} watch_context;

static void fen_callback(const chessnut_ble_event *event, void *user_data) {
  watch_context *context = user_data;
  if (context != NULL && event->board_index >= 0 && event->board_index < 8) {
    int idx = event->board_index;
    if (!context->all_reports && strcmp(context->last_fen[idx], event->fen) == 0) {
      context->duplicate_count[idx]++;
      return;
    }
    if (context->duplicate_count[idx] > 0) {
      printf("Board %d: %lu unchanged report(s) suppressed\n",
             idx,
             context->duplicate_count[idx]);
      context->duplicate_count[idx] = 0;
    }
    snprintf(context->last_fen[idx], sizeof(context->last_fen[idx]), "%s", event->fen);
  }

  printf("Board %d (%s %s): %s",
         event->board_index,
         event->name,
         event->identifier,
         event->fen);
  if (event->timestamp_ms != 0) {
    printf("  t=%ums", event->timestamp_ms);
  }
  printf("\n");
  fflush(stdout);
}

static int cmd_scan(int argc, char **argv) {
  chessnut_ble_options options;
  int rc = parse_options(argc, argv, 2, &options, NULL, NULL, NULL, NULL);
  if (rc != 0) {
    return rc;
  }

  chessnut_ble_device devices[64];
  size_t total = 0;
  char error[512];
  rc = chessnut_ble_scan(&options, devices, 64, &total, error, sizeof(error));
  if (rc != 0) {
    fprintf(stderr, "Scan failed: %s\n", error);
    return rc;
  }

  printf("Bluetooth scan complete: %zu device(s)%s\n",
         total,
         total > 64 ? " (first 64 shown)" : "");
  size_t shown = total < 64 ? total : 64;
  for (size_t i = 0; i < shown; i++) {
    printf("  [%zu] %s%s id=%s rssi=%d\n",
           i,
           devices[i].looks_like_chessnut ? "candidate: " : "",
           devices[i].name,
           devices[i].identifier,
           devices[i].rssi);
  }
  if (total == 0) {
    if (options.include_all_devices) {
      printf("No BLE advertisements were seen during the scan window.\n");
    } else {
      printf("No matching BLE boards were found. Try --all to confirm Bluetooth scanning works.\n");
    }
  }
  return 0;
}

static int cmd_watch(int argc, char **argv, bool verbose_default) {
  chessnut_ble_options options;
  bool all_reports = false;
  int rc = parse_options(argc, argv, 2, &options, NULL, &all_reports, NULL, NULL);
  if (rc != 0) {
    return rc;
  }
  if (verbose_default) {
    options.verbose = true;
  }

  char error[512];
  printf("Watching for %d Chessnut BLE board(s) for up to %d seconds\n",
         options.max_boards,
         options.timeout_seconds);
  watch_context context;
  memset(&context, 0, sizeof(context));
  context.all_reports = all_reports || verbose_default;
  rc = chessnut_ble_watch(&options, fen_callback, &context, error, sizeof(error));
  if (rc != 0) {
    fprintf(stderr, "Watch failed: %s\n", error);
    fprintf(stderr, "Hint: turn the board on in Bluetooth mode, close Chessnut/EasyLink apps, and grant Bluetooth permission to the app running this command.\n");
  }
  return rc;
}

static int cmd_led(int argc, char **argv) {
  chessnut_ble_options options;
  int hold_ms = 1000;
  const char **squares = NULL;
  size_t square_count = 0;
  int rc = parse_options(argc, argv, 2, &options, &hold_ms, NULL, &squares, &square_count);
  if (rc != 0) {
    return rc;
  }
  if (square_count == 0) {
    fprintf(stderr, "led requires at least one square, e.g. chessnut-ble led e2 e4\n");
    return 2;
  }

  uint8_t rows[8];
  chessnut_protocol_result result = chessnut_led_rows_from_squares(squares, square_count, rows);
  if (result != CHESSNUT_PROTOCOL_OK) {
    fprintf(stderr, "Invalid LED square list: %s\n", chessnut_protocol_error(result));
    return 2;
  }

  char error[512];
  rc = chessnut_ble_flash_leds(&options, rows, hold_ms, error, sizeof(error));
  if (rc != 0) {
    fprintf(stderr, "LED command failed: %s\n", error);
  }
  return rc;
}

int main(int argc, char **argv) {
  const char *log_path = NULL;
  const char *status_path = NULL;
  int first = 1;

  while (first < argc) {
    if (strcmp(argv[first], "--log") == 0 && first + 1 < argc) {
      log_path = argv[first + 1];
      first += 2;
    } else if (strcmp(argv[first], "--status") == 0 && first + 1 < argc) {
      status_path = argv[first + 1];
      first += 2;
    } else {
      break;
    }
  }

  if (redirect_to_log(log_path) != 0) {
    fprintf(stderr, "Could not redirect output to %s\n", log_path);
    return write_status_file(status_path, 1);
  }

  if (argc - first < 1 || strcmp(argv[first], "--help") == 0 || strcmp(argv[first], "-h") == 0) {
    usage(argc - first < 1 ? stderr : stdout);
    return write_status_file(status_path, argc - first < 1 ? 2 : 0);
  }

  int shifted_argc = argc - first + 1;
  char **shifted_argv = argv + first - 1;
  shifted_argv[0] = argv[0];

  int rc = 0;
  if (strcmp(shifted_argv[1], "scan") == 0) {
    rc = cmd_scan(shifted_argc, shifted_argv);
    return write_status_file(status_path, rc);
  }
  if (strcmp(shifted_argv[1], "watch") == 0) {
    rc = cmd_watch(shifted_argc, shifted_argv, false);
    return write_status_file(status_path, rc);
  }
  if (strcmp(shifted_argv[1], "probe") == 0) {
    rc = cmd_watch(shifted_argc, shifted_argv, true);
    return write_status_file(status_path, rc);
  }
  if (strcmp(shifted_argv[1], "led") == 0) {
    rc = cmd_led(shifted_argc, shifted_argv);
    return write_status_file(status_path, rc);
  }

  fprintf(stderr, "Unknown command: %s\n", shifted_argv[1]);
  usage(stderr);
  return write_status_file(status_path, 2);
}

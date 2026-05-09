#include "chessnut_ble.h"

#import <CoreBluetooth/CoreBluetooth.h>
#import <Foundation/Foundation.h>

#include <stdio.h>
#include <string.h>

static NSString *const kChessnutWriteCharacteristic = @"1B7E8272-2877-41C3-B46E-CF057C562023";
static NSString *const kChessnutMiscCharacteristic = @"1B7E8273-2877-41C3-B46E-CF057C562023";
static NSString *const kChessnutBoardCharacteristic = @"1B7E8262-2877-41C3-B46E-CF057C562023";
static NSString *const kChessnutOtbCharacteristic = @"1B7E8283-2877-41C3-B46E-CF057C562023";

typedef NS_ENUM(NSInteger, ChessnutRunMode) {
  ChessnutRunModeScan = 0,
  ChessnutRunModeWatch = 1,
  ChessnutRunModeLed = 2,
};

@class ChessnutRunner;

@interface ChessnutPeripheralState : NSObject <CBPeripheralDelegate>
@property(nonatomic, weak) ChessnutRunner *runner;
@property(nonatomic, strong) CBPeripheral *peripheral;
@property(nonatomic, strong) NSString *name;
@property(nonatomic, strong) NSString *identifier;
@property(nonatomic, assign) NSInteger boardIndex;
@property(nonatomic, strong) CBCharacteristic *writeCharacteristic;
@property(nonatomic, strong) CBCharacteristic *boardCharacteristic;
@property(nonatomic, strong) CBCharacteristic *miscCharacteristic;
@property(nonatomic, strong) CBCharacteristic *otbCharacteristic;
@property(nonatomic, assign) BOOL initialized;
@property(nonatomic, assign) BOOL wroteLedOn;
- (instancetype)initWithPeripheral:(CBPeripheral *)peripheral
                              name:(NSString *)name
                             index:(NSInteger)index
                            runner:(ChessnutRunner *)runner;
- (void)maybeInitialize;
@end

@interface ChessnutRunner : NSObject <CBCentralManagerDelegate>
@property(nonatomic, assign) ChessnutRunMode mode;
@property(nonatomic, assign) chessnut_ble_options options;
@property(nonatomic, assign) chessnut_ble_fen_callback callback;
@property(nonatomic, assign) void *userData;
@property(nonatomic, assign) char *errorBuffer;
@property(nonatomic, assign) size_t errorLen;
@property(nonatomic, assign) BOOL done;
@property(nonatomic, assign) BOOL scanStarted;
@property(nonatomic, assign) BOOL scanStopped;
@property(nonatomic, assign) BOOL verbose;
@property(nonatomic, assign) NSInteger fenEvents;
@property(nonatomic, assign) NSInteger connectedCount;
@property(nonatomic, assign) NSInteger targetBoards;
@property(nonatomic, strong) CBCentralManager *central;
@property(nonatomic, strong) NSMutableArray<NSDictionary *> *seen;
@property(nonatomic, strong) NSMutableDictionary<NSUUID *, ChessnutPeripheralState *> *states;
@property(nonatomic, strong) NSData *ledCommand;
@property(nonatomic, assign) int ledHoldMilliseconds;
- (instancetype)initWithMode:(ChessnutRunMode)mode
                     options:(const chessnut_ble_options *)options
                    callback:(chessnut_ble_fen_callback)callback
                    userData:(void *)userData
                       error:(char *)error
                    errorLen:(size_t)errorLen;
- (void)start;
- (void)stopScan;
- (BOOL)matchesDeviceName:(NSString *)name;
- (void)setError:(NSString *)message;
- (void)log:(NSString *)message;
- (void)recordFenEventFromState:(ChessnutPeripheralState *)state
                             fen:(const char *)fen
                     timestampMs:(uint32_t)timestampMs;
- (void)writeData:(NSData *)data toState:(ChessnutPeripheralState *)state;
- (void)finishLedRunForState:(ChessnutPeripheralState *)state;
@end

static NSString *safe_name(CBPeripheral *peripheral, NSDictionary<NSString *, id> *advertisementData) {
  NSString *name = peripheral.name;
  NSString *localName = advertisementData[CBAdvertisementDataLocalNameKey];
  if (localName.length > 0) {
    name = localName;
  }
  if (name.length == 0) {
    name = @"(unnamed BLE device)";
  }
  return name;
}

static BOOL uuid_equals(CBUUID *uuid, NSString *expected) {
  return [[uuid.UUIDString uppercaseString] isEqualToString:[expected uppercaseString]];
}

static void copy_nsstring(NSString *source, char *dest, size_t destLen) {
  if (dest == NULL || destLen == 0) {
    return;
  }
  const char *utf8 = source.UTF8String != NULL ? source.UTF8String : "";
  snprintf(dest, destLen, "%s", utf8);
}

static bool looks_like_chessnut_name(NSString *name) {
  if (name.length == 0) {
    return false;
  }
  NSString *lower = name.lowercaseString;
  return [lower containsString:@"chessnut"] || [lower containsString:@"smart chess"];
}

chessnut_ble_options chessnut_ble_default_options(void) {
  chessnut_ble_options options;
  options.timeout_seconds = 12;
  options.max_boards = 1;
  options.verbose = false;
  options.include_all_devices = false;
  options.name_filter = NULL;
  return options;
}

@implementation ChessnutPeripheralState

- (instancetype)initWithPeripheral:(CBPeripheral *)peripheral
                              name:(NSString *)name
                             index:(NSInteger)index
                            runner:(ChessnutRunner *)runner {
  self = [super init];
  if (self) {
    _peripheral = peripheral;
    _name = name;
    _identifier = peripheral.identifier.UUIDString;
    _boardIndex = index;
    _runner = runner;
    _peripheral.delegate = self;
  }
  return self;
}

- (void)maybeInitialize {
  if (self.initialized || self.writeCharacteristic == nil || self.boardCharacteristic == nil) {
    return;
  }

  if ((self.boardCharacteristic.properties & CBCharacteristicPropertyNotify) != 0 ||
      (self.boardCharacteristic.properties & CBCharacteristicPropertyIndicate) != 0) {
    [self.peripheral setNotifyValue:YES forCharacteristic:self.boardCharacteristic];
  }
  if (self.miscCharacteristic != nil &&
      ((self.miscCharacteristic.properties & CBCharacteristicPropertyNotify) != 0 ||
       (self.miscCharacteristic.properties & CBCharacteristicPropertyIndicate) != 0)) {
    [self.peripheral setNotifyValue:YES forCharacteristic:self.miscCharacteristic];
  }
  if (self.otbCharacteristic != nil &&
      ((self.otbCharacteristic.properties & CBCharacteristicPropertyNotify) != 0 ||
       (self.otbCharacteristic.properties & CBCharacteristicPropertyIndicate) != 0)) {
    [self.peripheral setNotifyValue:YES forCharacteristic:self.otbCharacteristic];
  }

  NSData *init = [NSData dataWithBytes:CHESSNUT_CMD_REALTIME length:sizeof(CHESSNUT_CMD_REALTIME)];
  [self.runner writeData:init toState:self];
  self.initialized = YES;
  [self.runner log:[NSString stringWithFormat:@"Board %ld initialized with realtime command 21 01 00",
                                              (long)self.boardIndex]];

  if (self.runner.mode == ChessnutRunModeLed && self.runner.ledCommand != nil && !self.wroteLedOn) {
    self.wroteLedOn = YES;
    [self.runner writeData:self.runner.ledCommand toState:self];
    [self.runner finishLedRunForState:self];
  }
}

- (void)peripheral:(CBPeripheral *)peripheral didDiscoverServices:(NSError *)error {
  if (error != nil) {
    [self.runner setError:[NSString stringWithFormat:@"Could not discover GATT services on %@: %@",
                                                     self.name, error.localizedDescription]];
    return;
  }
  for (CBService *service in peripheral.services) {
    [self.runner log:[NSString stringWithFormat:@"Board %ld service %@",
                                                (long)self.boardIndex, service.UUID.UUIDString]];
    [peripheral discoverCharacteristics:nil forService:service];
  }
}

- (void)peripheral:(CBPeripheral *)peripheral
    didDiscoverCharacteristicsForService:(CBService *)service
                                   error:(NSError *)error {
  if (error != nil) {
    [self.runner setError:[NSString stringWithFormat:@"Could not discover characteristics on %@: %@",
                                                     self.name, error.localizedDescription]];
    return;
  }

  for (CBCharacteristic *characteristic in service.characteristics) {
    [self.runner log:[NSString stringWithFormat:@"Board %ld characteristic %@ props=0x%lx",
                                                (long)self.boardIndex,
                                                characteristic.UUID.UUIDString,
                                                (unsigned long)characteristic.properties]];
    if (uuid_equals(characteristic.UUID, kChessnutWriteCharacteristic)) {
      self.writeCharacteristic = characteristic;
    } else if (uuid_equals(characteristic.UUID, kChessnutBoardCharacteristic)) {
      self.boardCharacteristic = characteristic;
    } else if (uuid_equals(characteristic.UUID, kChessnutMiscCharacteristic)) {
      self.miscCharacteristic = characteristic;
    } else if (uuid_equals(characteristic.UUID, kChessnutOtbCharacteristic)) {
      self.otbCharacteristic = characteristic;
    }

    if (self.writeCharacteristic == nil &&
        ((characteristic.properties & CBCharacteristicPropertyWrite) != 0 ||
         (characteristic.properties & CBCharacteristicPropertyWriteWithoutResponse) != 0)) {
      self.writeCharacteristic = characteristic;
    }
    if (self.boardCharacteristic == nil &&
        ((characteristic.properties & CBCharacteristicPropertyNotify) != 0 ||
         (characteristic.properties & CBCharacteristicPropertyIndicate) != 0)) {
      self.boardCharacteristic = characteristic;
    }
  }

  [self maybeInitialize];
}

- (void)peripheral:(CBPeripheral *)peripheral
    didUpdateNotificationStateForCharacteristic:(CBCharacteristic *)characteristic
                                         error:(NSError *)error {
  (void)peripheral;
  if (error != nil) {
    [self.runner log:[NSString stringWithFormat:@"Notify failed for %@ on board %ld: %@",
                                                characteristic.UUID.UUIDString,
                                                (long)self.boardIndex,
                                                error.localizedDescription]];
  }
}

- (void)peripheral:(CBPeripheral *)peripheral
    didUpdateValueForCharacteristic:(CBCharacteristic *)characteristic
                              error:(NSError *)error {
  (void)peripheral;
  if (error != nil) {
    [self.runner log:[NSString stringWithFormat:@"Read failed for %@ on board %ld: %@",
                                                characteristic.UUID.UUIDString,
                                                (long)self.boardIndex,
                                                error.localizedDescription]];
    return;
  }

  NSData *value = characteristic.value;
  if (value.length == 0) {
    return;
  }

  const uint8_t *bytes = value.bytes;
  if (self.runner.verbose) {
    NSMutableString *hex = [NSMutableString string];
    for (NSUInteger i = 0; i < value.length; i++) {
      [hex appendFormat:@"%02x%@", bytes[i], i + 1 == value.length ? @"" : @" "];
    }
    [self.runner log:[NSString stringWithFormat:@"Board %ld notify %@: %@",
                                                (long)self.boardIndex,
                                                characteristic.UUID.UUIDString,
                                                hex]];
  }

  char fen[CHESSNUT_FEN_MAX];
  chessnut_protocol_result result = chessnut_report_to_fen(bytes, value.length, fen, sizeof(fen));
  if (result == CHESSNUT_PROTOCOL_OK) {
    uint32_t timestamp = 0;
    if (value.length >= CHESSNUT_BLE_BOARD_REPORT_LEN) {
      timestamp = (uint32_t)bytes[34] | ((uint32_t)bytes[35] << 8) |
                  ((uint32_t)bytes[36] << 16) | ((uint32_t)bytes[37] << 24);
    }
    [self.runner recordFenEventFromState:self fen:fen timestampMs:timestamp];
    return;
  }

  int percent = 0;
  bool charging = false;
  if (chessnut_battery_from_report(bytes, value.length, &percent, &charging) ==
      CHESSNUT_PROTOCOL_OK) {
    printf("Board %ld battery: %d%% %s\n",
           (long)self.boardIndex,
           percent,
           charging ? "(charging)" : "");
    fflush(stdout);
  }
}

@end

@implementation ChessnutRunner

- (instancetype)initWithMode:(ChessnutRunMode)mode
                     options:(const chessnut_ble_options *)options
                    callback:(chessnut_ble_fen_callback)callback
                    userData:(void *)userData
                       error:(char *)error
                    errorLen:(size_t)errorLen {
  self = [super init];
  if (self) {
    _mode = mode;
    _options = options != NULL ? *options : chessnut_ble_default_options();
    if (_options.timeout_seconds <= 0) {
      _options.timeout_seconds = chessnut_ble_default_options().timeout_seconds;
    }
    if (_options.max_boards <= 0) {
      _options.max_boards = 1;
    }
    _targetBoards = _options.max_boards;
    _verbose = _options.verbose;
    _callback = callback;
    _userData = userData;
    _errorBuffer = error;
    _errorLen = errorLen;
    _seen = [NSMutableArray array];
    _states = [NSMutableDictionary dictionary];
  }
  return self;
}

- (void)start {
  self.central = [[CBCentralManager alloc] initWithDelegate:self queue:nil];
}

- (void)setError:(NSString *)message {
  if (self.errorBuffer != NULL && self.errorLen > 0) {
    const char *utf8 = message.UTF8String != NULL ? message.UTF8String : "unknown CoreBluetooth error";
    snprintf(self.errorBuffer, self.errorLen, "%s", utf8);
  }
  self.done = YES;
}

- (void)log:(NSString *)message {
  if (!self.verbose) {
    return;
  }
  fprintf(stderr, "%s\n", message.UTF8String != NULL ? message.UTF8String : "");
}

- (BOOL)matchesDeviceName:(NSString *)name {
  if (self.options.name_filter != NULL && strlen(self.options.name_filter) > 0) {
    NSString *filter = [NSString stringWithUTF8String:self.options.name_filter];
    return [[name lowercaseString] containsString:[filter lowercaseString]];
  }
  if (self.options.include_all_devices) {
    return YES;
  }
  return looks_like_chessnut_name(name);
}

- (void)stopScan {
  if (!self.scanStopped && self.scanStarted) {
    [self.central stopScan];
    self.scanStopped = YES;
  }
}

- (void)centralManagerDidUpdateState:(CBCentralManager *)central {
  switch (central.state) {
  case CBManagerStatePoweredOn:
    self.scanStarted = YES;
    [self log:@"Bluetooth powered on; scanning"];
    [central scanForPeripheralsWithServices:nil
                                    options:@{CBCentralManagerScanOptionAllowDuplicatesKey : @NO}];
    break;
  case CBManagerStateUnauthorized:
    [self setError:@"Bluetooth is not authorized. On macOS, grant Bluetooth permission to Terminal, iTerm, VS Code, or Codex in System Settings > Privacy & Security > Bluetooth, then restart the app."];
    break;
  case CBManagerStatePoweredOff:
    [self setError:@"Bluetooth is powered off. Turn Bluetooth on in macOS Control Center or System Settings."];
    break;
  case CBManagerStateUnsupported:
    [self setError:@"This Mac does not report CoreBluetooth support."];
    break;
  default:
    [self log:[NSString stringWithFormat:@"Bluetooth state is %ld; waiting", (long)central.state]];
    break;
  }
}

- (void)centralManager:(CBCentralManager *)central
 didDiscoverPeripheral:(CBPeripheral *)peripheral
     advertisementData:(NSDictionary<NSString *, id> *)advertisementData
                  RSSI:(NSNumber *)RSSI {
  NSString *name = safe_name(peripheral, advertisementData);
  BOOL isMatch = [self matchesDeviceName:name];
  BOOL looksLikeChessnut = looks_like_chessnut_name(name);
  if (!isMatch && self.mode != ChessnutRunModeScan) {
    return;
  }
  if (!isMatch && self.mode == ChessnutRunModeScan && !self.options.include_all_devices) {
    return;
  }

  BOOL alreadySeen = NO;
  for (NSDictionary *entry in self.seen) {
    if ([entry[@"identifier"] isEqualToString:peripheral.identifier.UUIDString]) {
      alreadySeen = YES;
      break;
    }
  }
  if (!alreadySeen) {
    [self.seen addObject:@{
      @"name" : name,
      @"identifier" : peripheral.identifier.UUIDString,
      @"rssi" : RSSI != nil ? RSSI : @0,
      @"looksLikeChessnut" : @(looksLikeChessnut)
    }];
    [self log:[NSString stringWithFormat:@"Discovered %@ %@ RSSI %@",
                                         looksLikeChessnut ? @"Chessnut-like" : @"BLE",
                                         name,
                                         RSSI]];
  }

  if (self.mode == ChessnutRunModeScan || !isMatch) {
    return;
  }
  if (self.connectedCount >= self.targetBoards) {
    [self stopScan];
    return;
  }
  if (self.states[peripheral.identifier] != nil) {
    return;
  }

  NSInteger index = self.connectedCount;
  ChessnutPeripheralState *state = [[ChessnutPeripheralState alloc] initWithPeripheral:peripheral
                                                                                  name:name
                                                                                 index:index
                                                                                runner:self];
  self.states[peripheral.identifier] = state;
  self.connectedCount++;
  [self log:[NSString stringWithFormat:@"Connecting board %ld: %@ %@",
                                       (long)index,
                                       name,
                                       peripheral.identifier.UUIDString]];
  [central connectPeripheral:peripheral options:nil];
  if (self.connectedCount >= self.targetBoards) {
    [self stopScan];
  }
}

- (void)centralManager:(CBCentralManager *)central
  didConnectPeripheral:(CBPeripheral *)peripheral {
  (void)central;
  ChessnutPeripheralState *state = self.states[peripheral.identifier];
  [self log:[NSString stringWithFormat:@"Connected %@",
                                       state.name != nil ? state.name : peripheral.identifier.UUIDString]];
  [peripheral discoverServices:nil];
}

- (void)centralManager:(CBCentralManager *)central
didFailToConnectPeripheral:(CBPeripheral *)peripheral
                 error:(NSError *)error {
  (void)central;
  [self setError:[NSString stringWithFormat:@"Failed to connect to %@: %@",
                                            peripheral.name != nil ? peripheral.name : peripheral.identifier.UUIDString,
                                            error.localizedDescription != nil ? error.localizedDescription : @"unknown error"]];
}

- (void)centralManager:(CBCentralManager *)central
 didDisconnectPeripheral:(CBPeripheral *)peripheral
                  error:(NSError *)error {
  (void)central;
  [self log:[NSString stringWithFormat:@"Disconnected %@%@%@",
                                       peripheral.name != nil ? peripheral.name : peripheral.identifier.UUIDString,
                                       error == nil ? @"" : @": ",
                                       error.localizedDescription != nil ? error.localizedDescription : @""]];
}

- (void)writeData:(NSData *)data toState:(ChessnutPeripheralState *)state {
  if (state.writeCharacteristic == nil) {
    return;
  }
  CBCharacteristicWriteType writeType =
      (state.writeCharacteristic.properties & CBCharacteristicPropertyWriteWithoutResponse) != 0
          ? CBCharacteristicWriteWithoutResponse
          : CBCharacteristicWriteWithResponse;
  [state.peripheral writeValue:data forCharacteristic:state.writeCharacteristic type:writeType];
}

- (void)recordFenEventFromState:(ChessnutPeripheralState *)state
                             fen:(const char *)fen
                     timestampMs:(uint32_t)timestampMs {
  self.fenEvents++;
  if (self.callback != NULL) {
    chessnut_ble_event event;
    memset(&event, 0, sizeof(event));
    event.board_index = (int)state.boardIndex;
    copy_nsstring(state.name, event.name, sizeof(event.name));
    copy_nsstring(state.identifier, event.identifier, sizeof(event.identifier));
    snprintf(event.fen, sizeof(event.fen), "%s", fen);
    event.timestamp_ms = timestampMs;
    self.callback(&event, self.userData);
  }
}

- (void)finishLedRunForState:(ChessnutPeripheralState *)state {
  int hold = self.ledHoldMilliseconds > 0 ? self.ledHoldMilliseconds : 1000;
  dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)hold * NSEC_PER_MSEC),
                 dispatch_get_main_queue(), ^{
                   uint8_t rows[8] = {0};
                   uint8_t command[CHESSNUT_LED_COMMAND_LEN];
                   chessnut_make_led_command(rows, command);
                   NSData *off = [NSData dataWithBytes:command length:sizeof(command)];
                   [self writeData:off toState:state];
                   self.done = YES;
                 });
}

@end

static int run_loop_until_done(ChessnutRunner *runner, int timeout_seconds) {
  NSDate *deadline = [NSDate dateWithTimeIntervalSinceNow:timeout_seconds];
  [runner start];
  while (!runner.done && [deadline timeIntervalSinceNow] > 0) {
    @autoreleasepool {
      [[NSRunLoop currentRunLoop] runMode:NSDefaultRunLoopMode
                               beforeDate:[NSDate dateWithTimeIntervalSinceNow:0.05]];
    }
  }
  [runner stopScan];
  if (!runner.done && runner.errorBuffer != NULL && runner.errorLen > 0) {
    if (runner.mode == ChessnutRunModeScan) {
      return 0;
    }
    snprintf(runner.errorBuffer, runner.errorLen, "Timed out after %d seconds", timeout_seconds);
  }
  return runner.done ? 0 : 2;
}

int chessnut_ble_scan(const chessnut_ble_options *options,
                      chessnut_ble_device *devices,
                      size_t capacity,
                      size_t *device_count,
                      char *error,
                      size_t error_len) {
  if (device_count == NULL || (capacity > 0 && devices == NULL)) {
    if (error != NULL && error_len > 0) {
      snprintf(error, error_len, "invalid scan output buffer");
    }
    return 1;
  }
  *device_count = 0;
  if (error != NULL && error_len > 0) {
    error[0] = '\0';
  }

  @autoreleasepool {
    ChessnutRunner *runner = [[ChessnutRunner alloc] initWithMode:ChessnutRunModeScan
                                                          options:options
                                                         callback:NULL
                                                         userData:NULL
                                                            error:error
                                                         errorLen:error_len];
    int rc = run_loop_until_done(runner, runner.options.timeout_seconds);
    if (error != NULL && error[0] != '\0' && rc != 2) {
      return 1;
    }

    size_t seenCount = runner.seen.count;
    size_t count = capacity < seenCount ? capacity : seenCount;
    for (size_t i = 0; i < count; i++) {
      NSDictionary *entry = runner.seen[i];
      memset(&devices[i], 0, sizeof(devices[i]));
      copy_nsstring(entry[@"name"], devices[i].name, sizeof(devices[i].name));
      copy_nsstring(entry[@"identifier"], devices[i].identifier, sizeof(devices[i].identifier));
      devices[i].rssi = [entry[@"rssi"] intValue];
      devices[i].looks_like_chessnut = [entry[@"looksLikeChessnut"] boolValue];
    }
    *device_count = runner.seen.count;
    if (rc == 2 && (error == NULL || error[0] == '\0')) {
      return 0;
    }
    return (error != NULL && error[0] != '\0' && ![ @(runner.seen.count > 0) boolValue]) ? 1 : 0;
  }
}

int chessnut_ble_watch(const chessnut_ble_options *options,
                       chessnut_ble_fen_callback callback,
                       void *user_data,
                       char *error,
                       size_t error_len) {
  if (error != NULL && error_len > 0) {
    error[0] = '\0';
  }
  @autoreleasepool {
    ChessnutRunner *runner = [[ChessnutRunner alloc] initWithMode:ChessnutRunModeWatch
                                                          options:options
                                                         callback:callback
                                                         userData:user_data
                                                            error:error
                                                         errorLen:error_len];
    int rc = run_loop_until_done(runner, runner.options.timeout_seconds);
    if (runner.fenEvents > 0) {
      return 0;
    }
    if (error != NULL && error_len > 0 &&
        (error[0] == '\0' || strncmp(error, "Timed out", strlen("Timed out")) == 0)) {
      if (runner.connectedCount == 0) {
        snprintf(error, error_len, "No Chessnut BLE boards were discovered. Make sure the board is on, not already connected to another app, and visible over Bluetooth.");
      } else {
        snprintf(error, error_len, "Connected to %ld board(s), but no board-state notifications arrived before timeout. The board may not have accepted realtime mode or the expected GATT characteristics may differ.",
                 (long)runner.connectedCount);
      }
    }
    return rc == 0 ? 2 : rc;
  }
}

int chessnut_ble_flash_leds(const chessnut_ble_options *options,
                            const uint8_t rows[8],
                            int hold_milliseconds,
                            char *error,
                            size_t error_len) {
  if (rows == NULL) {
    if (error != NULL && error_len > 0) {
      snprintf(error, error_len, "missing LED rows");
    }
    return 1;
  }
  if (error != NULL && error_len > 0) {
    error[0] = '\0';
  }

  uint8_t command[CHESSNUT_LED_COMMAND_LEN];
  chessnut_make_led_command(rows, command);

  @autoreleasepool {
    ChessnutRunner *runner = [[ChessnutRunner alloc] initWithMode:ChessnutRunModeLed
                                                          options:options
                                                         callback:NULL
                                                         userData:NULL
                                                            error:error
                                                         errorLen:error_len];
    runner.ledCommand = [NSData dataWithBytes:command length:sizeof(command)];
    runner.ledHoldMilliseconds = hold_milliseconds;
    int rc = run_loop_until_done(runner, runner.options.timeout_seconds);
    if (rc == 0) {
      return 0;
    }
    if (error != NULL && error_len > 0 && error[0] == '\0') {
      snprintf(error, error_len, "Could not connect and send LED command before timeout");
    }
    return rc;
  }
}

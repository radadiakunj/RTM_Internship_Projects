#pragma once
/*
 * Minimal PCF8574 I2C backpack driver for HD44780 16x2 LCD.
 * No external LiquidCrystal_I2C library required.
 */
#include <Wire.h>

class LcdI2c {
 public:
  LcdI2c(uint8_t addr, uint8_t cols, uint8_t rows)
      : _addr(addr), _cols(cols), _rows(rows), _backlight(0x08) {}

  bool begin(int sdaPin, int sclPin) {
    Wire.begin(sdaPin, sclPin);
    Wire.setClock(100000);
    delay(20);
    if (!probe()) return false;
    _write4(0x03);
    delay(5);
    _write4(0x03);
    delay(1);
    _write4(0x03);
    delay(1);
    _write4(0x02);
    _command(0x28);  // 4-bit, 2 lines, 5x8
    _command(0x0C);  // display on, cursor off
    _command(0x06);  // increment
    clear();
    return true;
  }

  bool probe() {
    Wire.beginTransmission(_addr);
    return Wire.endTransmission() == 0;
  }

  void clear() {
    _command(0x01);
    delay(2);
    _cursorCol = 0;
    _cursorRow = 0;
  }

  void setCursor(uint8_t col, uint8_t row) {
    static const uint8_t rowOffset[] = {0x00, 0x40, 0x14, 0x54};
    if (row >= _rows) row = _rows - 1;
    if (col >= _cols) col = _cols - 1;
    _command(0x80 | (col + rowOffset[row]));
    _cursorCol = col;
    _cursorRow = row;
  }

  void print(const char* text) {
    if (!text) return;
    while (*text) write(*text++);
  }

  void printLine(uint8_t row, const char* text) {
    setCursor(0, row);
    char buf[17];
    size_t n = strlen(text);
    if (n > _cols) n = _cols;
    memcpy(buf, text, n);
    for (size_t i = n; i < _cols; i++) buf[i] = ' ';
    buf[_cols] = '\0';
    print(buf);
  }

  void write(uint8_t ch) {
    _write(ch, true);
    _cursorCol++;
    if (_cursorCol >= _cols) {
      _cursorCol = 0;
      _cursorRow = (_cursorRow + 1) % _rows;
    }
  }

 private:
  uint8_t _addr;
  uint8_t _cols;
  uint8_t _rows;
  uint8_t _backlight;
  uint8_t _cursorCol = 0;
  uint8_t _cursorRow = 0;

  void _pulseEnable(uint8_t data) {
    Wire.beginTransmission(_addr);
    Wire.write(data | 0x04 | _backlight);
    Wire.endTransmission();
    delayMicroseconds(1);
    Wire.beginTransmission(_addr);
    Wire.write(data | _backlight);
    Wire.endTransmission();
    delayMicroseconds(50);
  }

  void _write4(uint8_t nibble) {
    nibble &= 0xF0;
    _pulseEnable(nibble);
    _pulseEnable(nibble << 4);
  }

  void _write(uint8_t value, bool rs) {
    uint8_t high = (value & 0xF0) | (rs ? 0x01 : 0x00);
    uint8_t low = ((value << 4) & 0xF0) | (rs ? 0x01 : 0x00);
    _pulseEnable(high);
    _pulseEnable(low);
  }

  void _command(uint8_t cmd) { _write(cmd, false); }
};

#include <avr/io.h>
#include <avr/pgmspace.h>
#include <avr/eeprom.h>
#include "example/foo.h"
#include "example/bar.h"

const uint8_t example_data EEMEM  = 100;
const uint8_t example_data2[] EEMEM  = {"This string is PROGMEM and will go into the eeprom data"};

int main(int argc, char **argv) {
  DDRA = 0x01;
  return foo() * bar() + eeprom_read_byte(&example_data);
}

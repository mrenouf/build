#include <avr/io.h>
#include <util/delay.h>

int foo() {
  DDRA = 1;
  _delay_ms(20);
  return 32;
}

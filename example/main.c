#include <avr/io.h>
#include "example/foo.h"
#include "example/bar.h"

int main(int argc, char **argv) {
  DDRA = 0x01;
  return foo() * bar();
}

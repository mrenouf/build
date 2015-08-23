import sys
sys.dont_write_bytecode = True

import copy
import fabricate
import os
from cc import CcLibraryRule, CcBinaryRule
from util import replace_ext

DEFAULT_CFLAGS = [
    "-Os",
    "-g",
    "-std=gnu99",
    "-Wall",
    "-funsigned-char",
    "-funsigned-bitfields",
    "-fpack-struct",
    "-fshort-enums",
    "-ffunction-sections",
    "-fdata-sections"
]

DEFAULT_LDFLAGS = [
    "-Wl,--gc-sections"
]


class AvrLibraryRule(CcLibraryRule):
    def __init__(self, module, name, sources=[], mcu='atmega8', freq=8000000, cflags=[], deps=[], *args, **kwargs):
        full_cflags = copy.copy(DEFAULT_CFLAGS)
        full_cflags.extend(["-mmcu=%s" % mcu, "-DF_CPU=%d" % freq])
        full_cflags.extend(cflags)
        super(AvrLibraryRule, self).__init__(module, name, sources, static=True, abi='avr', cflags=full_cflags, deps=deps, *args, **kwargs)


class AvrBinaryRule(CcBinaryRule):
    def __init__(self, module, name, sources=[], mcu='atmega8', freq=8000000, cflags=[], ldflags=[], deps=[], *args, **kwargs):
        self.mcu = mcu
        full_cflags = copy.copy(DEFAULT_CFLAGS)
        full_cflags.extend(["-mmcu=%s" % mcu, "-DF_CPU=%d" % freq])
        full_cflags.extend(cflags)
        super(AvrBinaryRule, self).__init__(module, name, sources=sources, static=True, abi='avr', cflags=full_cflags, ldflags=ldflags, deps=deps, *args, **kwargs)

    def link(self, target, ldflags, objfiles=[]):
        full_ldflags = copy.copy(DEFAULT_LDFLAGS)
        full_ldflags.append("-mmcu=%s" % self.mcu)        
        full_ldflags.append("-Wl,-Map,%s.map" % target)
        full_ldflags.extend(ldflags)
        elf = target + '.elf'
        super(AvrBinaryRule, self).link(elf, full_ldflags, objfiles)
        # hex image for flashing
        fabricate.run([["avr-objcopy", "-j", ".text", "-j", ".data", "-O", "ihex", elf, target + ".hex"]])
        # eeprom image
        fabricate.run([["avr-objcopy", "-j", ".eeprom", "--change-section-lma", ".eeprom=0", "-O", "ihex", elf, target + ".eeprom"]])
        # dump assembly listing
        fabricate.run([["avr-objdump", "-S", elf, ">", target + ".lst"]], shell=True)
        # show sizes
        fabricate.run([["avr-size", "-C", "--mcu=%s" % self.mcu, elf]])


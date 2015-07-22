import sys
sys.dont_write_bytecode = True

import fabricate
import os
#from rules import register_rule
from core import BuildRule
from util import replace_ext

class CcRule(BuildRule):
    ABI_CFLAGS = {
        'avr': '-Os -g -std=gnu99 -Wall -funsigned-char -funsigned-bitfields -fpack-struct -fshort-enums -ffunction-sections -fdata-sections'
    }

    ABI_LDFLAGS = {
        'avr': '-Wl,-Map,$(TARGET).map -Wl,--gc-sections'
    }

    def __init__(self, module, name, static=False, abi=None, cflags=None, deps=None, *args, **kwargs):
        super(CcRule, self).__init__(module, name, static, cflags, deps, abi=abi, *args, **kwargs)
        self.outputs = []
        self.static = static
        self.cflags = cflags
        self.deps = deps
        self.deprules = {}
        self.objfiles = []
        self.abi = abi

    def init(self):
        self.indir = os.path.relpath(self.module.buildroot + self.module.path)
        self.outdir = os.path.relpath(self.module.buildroot + '/' + os.path.normpath(os.path.join('out' + self.module.path, self.name)))
        if self.abi is None:
            self.abi = HOST_ABI
        self.cc = '%s-gcc' % (self.abi)
        self.ar = '%s-ar' % (self.abi)
        self.mkdirs(self.outdir)

    def compile(self, source):
        compile = [self.cc]
        compile.extend(["-I" + self.module.buildroot])
        compile.extend(self.cflags.split(" "))
        #compile.extend(self.ABI_CFLAGS[self.abi].split(" "))
        srcfile = os.path.join(self.indir, source)
        objfile = os.path.join(self.outdir, replace_ext(source, 'o'))
        #if self.cflags is not None:
        #    compile.extend(expand_make_vars(self.cflags, MAKE_VARS).split(" "))
        if not self.static:
            compile.append('-fpic')
        compile.extend(['-c', srcfile])
        compile.extend(['-o', objfile])
        self.objfiles.append(objfile)
        fabricate.run([compile])

    def link(self, target, objfiles=[]):
        link = [self.cc]
        link.extend(self.ldflags.split(" "))
        #???
        #link.extend(self.ABI_LDFLAGS[self.abi].split(" "))
	
        link.extend(['-o', target])
        link.extend(self.objfiles)
        for deps in self.deprules.values():
            for dep in deps:
                if isinstance(dep, CcLibraryRule):
                    if dep.static == True:
                        link.extend(dep.outputs)
                    else:
                        dirs = {}
                        for out in dep.outputs:
                            dirs[os.path.dirname(out)] = 1
                        for d in dirs.keys():
                            link.extend(['-L' + d])
                        link.extend(['-l' + dep.name])
                else:
                    raise ValueError("Unsupported dependency type %s" % (type(dep)))
        fabricate.run([link])


class CcLibraryRule(CcRule):
    def __init__(self, module, name, sources=[], static=False, cflags=None, *args, **kwargs):
        super(CcLibraryRule, self).__init__(module, name, *args, **kwargs)
        self.outputs = []
        self.sources = sources
        self.static = static
        self.cflags = cflags
        self.deprules = {}
        self.executed = False

    def do_execute(self):
        self.init()
        outfile = os.path.join(self.outdir, self.name + '.a')
        objfiles = []
        tasks = []

        for source in self.sources:
            self.compile(source)

        if self.static:
            libfile = os.path.join(self.outdir, self.name + '.a')
            archive = [self.ar, 'rc', os.path.join(self.outdir, self.name + '.a')]
            archive.extend(self.objfiles)
            fabricate.run([archive])
            self.add_output([libfile])
        else:
            libfile = os.path.join(self.outdir, 'lib' + self.name + '.so')
            sharedlib = [self.cc, '-shared', '-o', libfile]
            sharedlib.extend(self.objfiles)
            fabricate.run([sharedlib])
            self.add_output(libfile)

        for deps in self.deprules.values():
            for dep in deps:
                if isinstance(dep, CcLibraryRule):
                    self.add_outputs(dep.outputs)
                else:
                    raise ValueError("Unsupported dependency type %s" % (type(dep)))


class CcBinaryRule(CcRule):
    def __init__(self, module, name, sources=[], ldflags=None, *args, **kwargs):
        super(CcBinaryRule, self).__init__(module, name, *args, **kwargs)
        self.sources = sources
        self.ldflags = ldflags
        self.outputs = []
        self.deprules = {}

    def do_execute(self):
        self.init()
        outfile = os.path.join(self.outdir, self.name)
        objfiles = []
        tasks = []
        for source in self.sources:
            self.compile(source)
        self.link(os.path.join(self.outdir, self.name), objfiles)
        self.add_output(self.name)




import sys
sys.dont_write_bytecode = True

import fabricate
import os
#from rules import register_rule
from core import BuildRule
from util import replace_ext

class CcRule(BuildRule):
    def __init__(self, module, name, static=False, abi=None, cflags=[], ldflags=[], deps=[], *args, **kwargs):
        super(CcRule, self).__init__(module, name, deps, *args, **kwargs)
        self.outputs = []
        self.static = static
        self.cflags = cflags
        self.ldflags = ldflags
        self.deps = deps
        self.deprules = {}
        self.objfiles = []
        self.abi = abi

    def init(self):
        self.indir = os.path.relpath(self.module.buildroot + self.module.path)
        self.outdir = os.path.relpath(self.module.buildroot + '/' + os.path.normpath(os.path.join('out' + self.module.path, self.name)))
        if self.abi is None:
            self.abi = os.environ['HOST_ABI']
        self.cc = '%s-gcc' % (self.abi)
        self.ar = '%s-ar' % (self.abi)
        self.mkdirs(self.outdir)

    def compile(self, source):
        compile = [self.cc]
        compile.extend(["-I" + self.module.buildroot])
        compile.extend(self.cflags)
        srcfile = os.path.join(self.indir, source)
        objfile = os.path.join(self.outdir, replace_ext(source, 'o'))
        if not self.static:
            compile.append('-fpic')
        compile.extend(['-c', srcfile])
        compile.extend(['-o', objfile])
        self.objfiles.append(objfile)
        fabricate.run([compile])


class CcLibraryRule(CcRule):
    def __init__(self, module, name, sources, static=False, abi=None, cflags=[], deps=[], *args, **kwargs):
        super(CcLibraryRule, self).__init__(module, name, static, abi, cflags, ldflags=[], deps=deps, *args, **kwargs)
        self.sources = sources
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
    def __init__(self, module, name, sources=[], static=False, abi=None, cflags=[], ldflags=[], deps=[], *args, **kwargs):
        super(CcBinaryRule, self).__init__(module, name, static, abi, cflags, ldflags, deps, *args, **kwargs)
        self.sources = sources

    def do_execute(self):
        self.init()
        outfile = os.path.join(self.outdir, self.name)
        objfiles = []
        tasks = []
        for source in self.sources:
            self.compile(source)
        self.link(outfile, self.ldflags, objfiles)
        self.add_output(self.name)

    def link(self, target, ldflags, objfiles=[]):
        link = [self.cc]
        link.extend(ldflags)
        link.extend(['-o', target])
        link.extend(self.objfiles)
        for deps_key in self.deprules.keys():
            deps = self.deprules[deps_key]
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
                    raise ValueError("Unsupported link dependency ('%s') of type %s" % (deps_key, type(dep).__name__))
        fabricate.run([link])



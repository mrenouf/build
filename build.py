#!/usr/bin/python

import sys
sys.dont_write_bytecode = True

import argparse
import fabricate
from optparse import make_option
import os
import re
import shutil
import subprocess


RE_MAKE_VAR = re.compile(r'\$\(([A-Za-z0-9_-]+)\)')
RE_TARGET = re.compile(r'^(\/?(?:[0-9A-Za-z_]+)(?:(?:\/[0-9A-Za-z_]+)*))?(?:\:([0-9A-Za-z_]+))?$')

# TODO, make these args of build.py
MAKE_VARS = {'AVR_CHIP': 'atmega328p', 'AVR_FREQ': '12000000'}

# TODO, make this more flexible
BUILDROOT = os.path.dirname(os.path.realpath(__file__))

def get_gcc_target_machine(gcc='gcc'):
    try:
        return subprocess.check_output([gcc, '-dumpmachine'], shell=False).strip()
    except subprocess.CalledProcessError as e:
        print "Error: failed to identify machine type for toolchain '%s': %s" % (gcc, e.message)
        raise e
    except OSError as e:
        print "Error: failed to identify machine type for toolchain: '%s': %s" % (gcc, e.message)
        raise e


HOST_ABI = get_gcc_target_machine('gcc')

def expand_make_vars(text, values={}):
    def repl(m):
        try:
            return values[m.group(1)]
        except KeyError as e:
            raise ValueError('Undefined variable "%s" in "%s"' % (m.group(1), text))
    return RE_MAKE_VAR.sub(repl, text)

def replace_ext(fname, ext):
    return os.path.splitext(fname)[0] + '.' + ext

def file_ext(fname):
    return os.path.splitext(fname)[1]

def cross_tool(tool, cross):
    if cross is None:
        return tool
    if cross.endswith('-'):
        cross = cross[:-1]
    return "%s-%s" % (cross, tool)

class Module(object):
    def __init__(self, path, root=BUILDROOT):
        self.root = root
        self.path = path
        self.rules = {}
        self.eval_globals = {}

        # maps build file functions to a class to construct
        # the only required argument in the build file function is 'name'
        self.funcmap = {
            'cc_library': CcLibraryRule,
            'cc_binary': CcBinaryRule,
        }

        def make_call(module, classname, ruleclass):
            def call(name, *args, **kwargs):
                self.rules[name] = ruleclass(module, name, *args, **kwargs)
            return call

        for classname in self.funcmap.keys():
            self.eval_globals[classname] = make_call(self, classname, self.funcmap[classname])

    def __repr__(self):
        return type(self).__name__ + "(" + ", ".join(print_attrs(self, ['path', 'rules'])) + ")"

    def parse(self):
        eval_locals = {}
        execfile(self.root + '/' + self.path + '/' + 'module', self.eval_globals, eval_locals)

class BuildRule(object):
    def __init__(self, module, name, *args, **kwargs):
        self.module = module
        self.name = name
        self.deps = []
        self.outputs = []
        self.executed = False

    def add_task(self, command):
        self.tasks.append(command)

    def add_output(self, output):
        self.outputs.append(output)

    def execute(self):
        if not self.executed:
            self.executed = True
	    print "\nBuilding %s:%s" % (self.module.path, self.name)
            self.do_execute()

    def mkdirs(self, path):
        # Uses a shell conditional so fabricate can see the target dir as an input
        fabricate.run([['/bin/sh', '-c', '[ -d ' + path + ' ] || mkdir -p ' + path]], echo="mkdir -p %s" % (path))

class CcRule(BuildRule):
    def __init__(self, module, name, static=False, abi=None, cflags=None, deps=None, *args, **kwargs):
        super(CcRule, self).__init__(module, name, static, cflags, deps, abi=abi, *args, **kwargs)
        self.outputs = []
        self.static = static
        self.cflags = cflags
        self.deps = deps
        self.deprules = {}
        self.outfiles = None
        self.objfiles = []
        self.abi = abi

    def init(self):
        self.indir = os.path.relpath(BUILDROOT + self.module.path)
        self.outdir = os.path.relpath(BUILDROOT + '/' + os.path.normpath(os.path.join('out' + self.module.path, self.name)))
        if self.abi is None:
            self.abi = HOST_ABI
        self.cc = '%s-gcc' % (self.abi)
        self.ar = '%s-ar' % (self.abi)
        self.mkdirs(self.outdir)

    # TODO need to add header paths
    def compile(self, source):
        compile = [self.cc]
        srcfile = os.path.join(self.indir, source)
        objfile = os.path.join(self.outdir, replace_ext(source, 'o'))
        if self.cflags is not None:
            compile.extend(expand_make_vars(self.cflags, MAKE_VARS).split(" "))
        if not self.static:
            compile.append('-fpic')
        compile.extend(['-c', srcfile])
        compile.extend(['-o', objfile])
        self.objfiles.append(objfile)
        fabricate.run([compile])

    def link(self, target, objfiles=[]):
        link = [self.cc]
        link.extend(self.ldflags.split(" "))
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
        self.deps = []
        self.outputs = []
        self.sources = sources
        self.static = static
        self.cflags = cflags
        self.deprules = {}
        self.outfiles = None
        self.executed = False

    def do_execute(self):
        self.init()
        outfile = os.path.join(self.outdir, self.name + '.a')
        objfiles = []
        tasks = []

        # TODO add headers of dependency libraries
        for source in self.sources:
            self.compile(source)

        # TODO handle library <- library dependencies
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

        # TODO add headers of dependency libraries
        for source in self.sources:
            self.compile(source)

        self.link(os.path.join(self.outdir, self.name), objfiles)
        self.add_output(self.name)

def build():
    eval_targets(build.targets)

def parse_target_path_rule(target):
    m = RE_TARGET.match(target)
    if m is None:
        raise ValueError("%s is malformed" % (target))
    return (m.group(1), m.group(2))

def abs_module_path(relpath, path):
    if path is None:
        if relpath is None:
            return None
        return relpath
    if relpath is not None:
        if not os.path.isabs(path):
            path = os.path.join(relpath, path)
    if not path.startswith('/'):
        path = '/' + path
    return path

def eval_targets(targets, relpath=None, modules={}, queue=[]):
    for target in targets:
        eval_target(target, relpath, modules, queue)

def eval_target(target, relpath=None, modules={}, queue=[]):
    path, rulename = parse_target_path_rule(target)
    path = abs_module_path(relpath, path)
    try:
        module = modules[path]
    except KeyError:
        module = Module(path)
        try:
            module.parse()
        except IOError:
            raise ValueError('module %s does not exist' % (path))    
        modules[path] = module
    if rulename is None or rulename is "" or rulename == "all":
        deptargets = []
        for rule in module.rules.keys():
            deptargets.extend(eval_target(':' + rule, path, modules, queue))
	return deptargets
    else:
        try:
            rule = module.rules[rulename]
        except KeyError:
            raise ValueError('in %s: target %s could not be resolved' % (path + '/' + 'module', module.path + ':' + rulename))    
        if rule.deps is not None:
            # TODO: detect and abort on circular dependencies
            for dep in rule.deps:
                deptargets = eval_target(dep, path, modules, queue)
                rule.deprules[dep] = deptargets
        rule.execute()
    return [rule]

if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('targets', nargs='+')
    (options, args) = parser.parse_known_args()
    build.targets = options.targets
    os.chdir(BUILDROOT)
    fabricate.main(default="build", build_dir=os.getcwd(), command_line=args)




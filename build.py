#!/usr/bin/python

import sys
sys.dont_write_bytecode = True

import argparse
import fabricate
from optparse import make_option
import os
import shutil
import re


RE_MAKE_VAR = re.compile(r'\$\(([A-Za-z0-9_-]+)\)')
RE_TARGET = re.compile(r'^(\/?(?:[0-9A-Za-z_]+)(?:(?:\/[0-9A-Za-z_]+)*))?(?:\:([0-9A-Za-z_]+))?$')

# TODO, make these args of build.py
MAKE_VARS = {'AVR_CHIP': 'atmega328p', 'AVR_FREQ': '12000000'}

# TODO, make this more flexible
BUILDROOT = os.path.dirname(os.path.realpath(__file__))

def expand_make_vars(text, values={}):
    def repl(m):
        try:
            return values[m.group(1)]
        except KeyError as e:
            raise ValueError('Undefined variable %s' % text)
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

    def add_task(self, command):
        self.tasks.append(command)

    def add_output(self, output):
        self.outputs.append(output)


class CcLibraryRule(BuildRule):
    def __init__(self, module, name, sources=[], static=False, cross=None, cflags=None, deps=None, *args, **kwargs):
        super(CcLibraryRule, self).__init__(module, name, sources, static, cross, cflags, deps, *args, **kwargs)
        self.deps = []
        self.outputs = []
        self.sources = sources
        self.static = static
        self.cross = cross
        self.deps = deps
        self.cflags = cflags
        self.deps = deps
        self.deprules = {}
        self.outfiles = None
        self.executed = False

    def execute(self):
        indir = os.path.relpath(BUILDROOT + self.module.path)
        outdir = os.path.relpath(BUILDROOT + '/' + os.path.normpath(os.path.join('out' + self.module.path, self.name)))
        outfile = os.path.join(outdir, self.name + '.a')
        objfiles = []
        tasks = []

        cc = cross_tool('gcc', self.cross)
        ar = cross_tool('ar', self.cross)

        # Use shell conditional so fabricate can save the target dir as an input
        fabricate.run([['/bin/sh', '-c', '[ -d ' + outdir + ' ] || mkdir -p ' + outdir]])
        for source in self.sources:
            compile = [cc]
            srcfile = os.path.join(indir, source)
            objfile = os.path.join(outdir, replace_ext(source, 'o'))
            if self.cflags is not None:
                compile.extend(expand_make_vars(self.cflags, MAKE_VARS).split(" "))
            if not self.static:
                compile.append('-fpic')
            compile.extend(['-c', srcfile])
            compile.extend(['-o', objfile])
            objfiles.append(objfile)
            fabricate.run([compile])

        if self.static:
            libfile = os.path.join(outdir, self.name + '.a')
            archive = [ar, 'rc', os.path.join(outdir, self.name + '.a')]
            archive.extend(objfiles)
            fabricate.run([archive])
            self.add_output([libfile])
        else:
            libfile = os.path.join(outdir, 'lib' + self.name + '.so')
            sharedlib = [cc, '-shared', '-o', libfile]
            sharedlib.extend(objfiles)
            fabricate.run([sharedlib])
            self.add_output(libfile)

class CcBinaryRule(CcRule):
    def __init__(self, module, name, sources=[], cross=None, cflags=None, deps=None, *args, **kwargs):
        super(CcBinaryRule, self).__init__(module, name, sources, cross, cflags, deps, *args, **kwargs)
        self.sources = sources
        self.cross = cross
        self.cflags = cflags
        self.deps = deps
        self.outputs = []
        self.deprules = {}

    def execute(self):
        indir =  os.path.relpath(BUILDROOT + os.path.normpath(os.path.join(self.module.path)))
        outdir = os.path.relpath(BUILDROOT + '/' + os.path.normpath(os.path.join('out' + self.module.path, self.name)))
        outfile = os.path.join(outdir, self.name)
        objfiles = []
        tasks = []

        cc = cross_tool('gcc', self.cross)
        ar = cross_tool('ar', self.cross)

        # Use shell conditional so fabricate can save the target dir as an input
        fabricate.run([['/bin/sh', '-c', '[ -d ' + outdir + ' ] || mkdir -p ' + outdir]])
        for source in self.sources:
            compile = [cc]
            srcfile = os.path.join(indir, source)
            objfile = os.path.join(outdir, replace_ext(source, 'o'))
            if self.cflags is not None:
                compile.extend(expand_make_vars(self.cflags, MAKE_VARS).split(" "))
            compile.extend(['-c', srcfile])
            compile.extend(['-o', objfile])
            objfiles.append(objfile)
            fabricate.run([compile])

        link = [cc]
        link.extend(['-o', os.path.join(outdir, self.name)])
        link.extend(objfiles)

        for dep in self.deprules.values():
            if type(dep) is CcLibraryRule:
                if dep.static == True:
                    link.extend(dep.outputs)
                else:
                    dirs = {}
                    for out in dep.outputs:
                        dirs[os.path.dirname(out)] = 1
                    for d in dirs.keys():
                        link.extend(['-L' + d])
                    link.extend(['-l' + dep.name])

        fabricate.run([link])
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
        for rule in module.rules.keys():
            eval_target(':' + rule, path, modules, queue)
    else:
        try:
            rule = module.rules[rulename]
        except KeyError:
            raise ValueError('in %s: target %s could not be resolved' % (path + '/' + 'module', module.path + ':' + rulename))    
        if rule.deps is not None:
            # TODO: detect and abort on circular dependencies
            for dep in rule.deps:
                deptarget = eval_target(dep, path, modules, queue)
                rule.deprules[dep] = deptarget
        rule.execute()
    return rule

if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('targets', nargs='+')
    (options, args) = parser.parse_known_args()
    build.targets = options.targets
    os.chdir(BUILDROOT)
    fabricate.main(default="build", build_dir=os.getcwd(), command_line=args)




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

# Build rule classes
from rules import RULE_CLASSES

RE_TARGET = re.compile(r'^(\/?(?:[0-9A-Za-z_]+)(?:(?:\/[0-9A-Za-z_]+)*))?(?:\:([0-9A-Za-z_]+))?$')

# TODO, make these args of build.py
MAKE_VARS = {'AVR_CHIP': 'atmega328p', 'AVR_FREQ': '12000000'}

def get_gcc_target_machine(gcc='gcc'):
    try:
        return subprocess.check_output([gcc, '-dumpmachine'], shell=False).strip()
    except subprocess.CalledProcessError as e:
        print "Error: failed to identify machine type for toolchain '%s': %s" % (gcc, e.message)
        raise e
    except OSError as e:
        print "Error: failed to identify machine type for toolchain: '%s': %s" % (gcc, e.message)
        raise e

def find_buildroot(path=os.getcwd()):
    while not os.path.isfile(os.path.join(path, "MODULAR")):
        if path == "/":
            return None
        path = os.path.abspath(os.path.join(path, os.pardir))
    return path

HOST_ABI = get_gcc_target_machine('gcc')
os.environ['HOST_ABI'] = HOST_ABI

def cross_tool(tool, cross):
    if cross is None:
        return tool
    if cross.endswith('-'):
        cross = cross[:-1]
    return "%s-%s" % (cross, tool)


class Module(object):
    def __init__(self, path, root):
        self.root = root
        self.path = path
        self.rules = {}
        self.eval_globals = {}

        def make_call(module, classname, ruleclass):
            def call(name, *args, **kwargs):
                self.rules[name] = ruleclass(module, name, *args, **kwargs)
            return call

        for classname in RULE_CLASSES.keys():
            self.eval_globals[classname] = make_call(self, classname, RULE_CLASSES[classname])

    def __repr__(self):
        return type(self).__name__ + "(" + ", ".join(print_attrs(self, ['path', 'rules'])) + ")"

    def parse(self):
        eval_locals = {}
        execfile(self.root + '/' + self.path + '/' + 'module', self.eval_globals, eval_locals)


def build():
    eval_targets(build.targets, root=build.root, relpath=build.relpath)

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

def eval_targets(targets, root, relpath=None, modules={}, queue=[]):
    for target in targets:
        eval_target(target, root, relpath, modules, queue)

def eval_target(target, root, relpath=None, modules={}, queue=[]):
    path, rulename = parse_target_path_rule(target)
    path = abs_module_path(relpath, path)
    try:
        module = modules[path]
    except KeyError:
        module = Module(path, root)
        try:
            module.parse()
        except IOError:
            raise ValueError('module %s does not exist' % (path))    
        modules[path] = module

    if rulename is None:
        rulename = os.path.basename(path)

    if rulename == "all":
        deptargets = []
        for rule in module.rules.keys():
            deptargets.extend(eval_target(':' + rule, root, path, modules, queue))
	return deptargets
    else:
        try:
            rule = module.rules[rulename]
        except KeyError:
            raise ValueError('in %s: target %s could not be resolved' % (path + '/' + 'module', module.path + ':' + rulename))    
        # TODO: detect and abort on circular dependencies
        for dep in rule.deps:
            deptargets = eval_target(dep, root, path, modules, queue)
            rule.deprules[dep] = deptargets
        rule.execute()
    return [rule]

def module_relative_path(buildroot, path):
    relpath = os.path.relpath(os.getcwd() + '/', buildroot)
    if relpath == ".":
        return None
    return "/" + relpath

if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('command', nargs=1)    
    parser.add_argument('targets', nargs='+')
    (options, args) = parser.parse_known_args()
    build.targets = options.targets
    build.root = find_buildroot()
    if build.root is None:
        raise AssertionError("Could not locate the buildroot")
    build.relpath = module_relative_path(build.root, os.getcwd())
    os.chdir(build.root)
    fabricate.main(default="build", build_dir=os.getcwd(), command_line=args)



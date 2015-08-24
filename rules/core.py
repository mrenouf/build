import fabricate
import os

class BuildRule(object):
    def __init__(self, module, name, deps=[], *args, **kwargs):
        self.module = module
        self.name = name
        self.deps = deps
        self.outputs = []
        self.executed = False

    def init(self):
        self.indir = os.path.relpath(self.module.buildroot + self.module.path)
        self.outroot = os.path.relpath(self.module.buildroot + '/out')
        self.outdir = os.path.normpath(os.path.join(self.outroot + self.module.path, self.name))

    def mkdirs(self, path):
        # Uses a shell conditional so fabricate can see the target dir as an input
        fabricate.run([['/bin/sh', '-c', '[ -d ' + path + ' ] || mkdir -p ' + path]], echo="mkdir -p %s" % (path))

    def add_output(self, output):
        self.outputs.append(output)

    def add_outputs(self, outputs=[]):
        self.outputs.extend(outputs)

    def execute(self):
        if not self.executed:
            self.executed = True
	    print "\nBuilding %s:%s" % (self.module.path, self.name)
            self.do_execute()

    def do_execute(self):
        pass

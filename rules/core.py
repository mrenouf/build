import fabricate
import os

class BuildRule(object):
    def __init__(self, module, name, *args, **kwargs):
        self.module = module
        self.name = name
        self.deps = []
        self.outputs = []
        self.executed = False


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

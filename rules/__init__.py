from cc import CcLibraryRule, CcBinaryRule
from avr import AvrLibraryRule, AvrBinaryRule

# Used by the build system to map module functions to classes
RULE_CLASSES = {}

# maps build file functions to a class to construct
# the only required argument in the build file function is 'name'
def register_rule(name, classname):
    RULE_CLASSES[name] = classname


register_rule('cc_library', CcLibraryRule)
register_rule('cc_binary', CcBinaryRule)
register_rule('avr_library', AvrLibraryRule)
register_rule('avr_binary', AvrBinaryRule)


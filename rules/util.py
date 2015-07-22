import os

def replace_ext(fname, ext):
    return os.path.splitext(fname)[0] + '.' + ext

def file_ext(fname):
    return os.path.splitext(fname)[1]

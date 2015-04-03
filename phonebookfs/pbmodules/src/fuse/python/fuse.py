#
#    Copyright (C) 2001  Jeff Epler  <jepler@unpythonic.dhs.org>
#
#    This program can be distributed under the terms of the GNU GPL.
#    See the file COPYING.
#


# suppress version mismatch warnings
try:
    import warnings
    warnings.filterwarnings('ignore',
                            'Python C API version mismatch',
                            RuntimeWarning,
                            )
except:
    pass
 
from _fuse import main, DEBUG
import os, sys
from errno import *

class ErrnoWrapper:
    def __init__(self, func):
    	self.func = func
    def __call__(self, *args, **kw):
    	try:
    		return apply(self.func, args, kw)
    	except (IOError, OSError), detail:
    		# Sometimes this is an int, sometimes an instance...
    		if hasattr(detail, "errno"): detail = detail.errno
    		return -detail
class Fuse:

    _attrs = ['getattr', 'readlink', 'getdir', 'mknod', 'mkdir',
    	  'unlink', 'rmdir', 'symlink', 'rename', 'link', 'chmod',
    	  'chown', 'truncate', 'utime', 'open', 'read', 'write', 'release',
          'statfs', 'fsync']

    flags = 0
    multithreaded = 0

    def __init__(self, *args, **kw):

        # default attributes
        self.optlist = []
        self.optdict = {}
        self.mountpoint = None

        # grab arguments, if any
        argv = sys.argv
        argc = len(argv)
        if argc > 1:
            # we've been given the mountpoint
            self.mountpoint = argv[1]
        if argc > 2:
            # we've received mount args
            optstr = argv[2]
            opts = optstr.split(",")
            for o in opts:
                try:
                    k, v = o.split("=", 1)
                    self.optdict[k] = v
                except:
                    self.optlist.append(o)
    def main(self):
    	d = {'flags': self.flags}
    	d['multithreaded'] = self.multithreaded
    	for a in self._attrs:
    		if hasattr(self,a):
    			d[a] = ErrnoWrapper(getattr(self, a))
    	apply(main, (), d)

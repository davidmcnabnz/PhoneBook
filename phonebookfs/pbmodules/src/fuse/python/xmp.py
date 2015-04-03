#!/usr/bin/env python
#
#    Copyright (C) 2001  Jeff Epler  <jepler@unpythonic.dhs.org>
#
#    This program can be distributed under the terms of the GNU GPL.
#    See the file COPYING.
#


from fuse import Fuse
import os
from errno import *
from stat import *

import thread
class Xmp(Fuse):

    def __init__(self, *args, **kw):

        Fuse.__init__(self, *args, **kw)

        if 0:
            print "xmp.py:Xmp:mountpoint: %s" % repr(self.mountpoint)
            print "xmp.py:Xmp:unnamed mount options: %s" % self.optlist
            print "xmp.py:Xmp:named mount options: %s" % self.optdict

        # do stuff to set up your filesystem here, if you want
        #thread.start_new_thread(self.mythread, ())
        pass
    def mythread(self):

        """
        The beauty of the FUSE python implementation is that with the python interp
        running in foreground, you can have threads
        """    
        print "mythread: started"
        #while 1:
        #    time.sleep(120)
        #    print "mythread: ticking"

    flags = 1

    def getattr(self, path):
        return os.lstat(path)
    def readlink(self, path):
        print "readlink: path='%s'" % path
        return os.readlink(path)
    def getdir(self, path):
        return map(lambda x: (x,0), os.listdir(path))
    def unlink(self, path):
        return os.unlink(path)
    def rmdir(self, path):
        return os.rmdir(path)
    def symlink(self, path, path1):
        print "symlink: path='%s', path1='%s'" % (path, path1)
        return os.symlink(path, path1)
    def rename(self, path, path1):
        return os.rename(path, path1)
    def link(self, path, path1):
        return os.link(path, path1)
    def chmod(self, path, mode):
        return os.chmod(path, mode)
    def chown(self, path, user, group):
        return os.chown(path, user, group)
    def truncate(self, path, size):
        f = open(path, "w+")
        return f.truncate(size)
    def mknod(self, path, mode, dev):
        """ Python has no os.mknod, so we can only do some things """
        if S_ISREG(mode):
            open(path, "w")
        else:
            return -EINVAL
    def mkdir(self, path, mode):
        return os.mkdir(path, mode)
    def utime(self, path, times):
        return os.utime(path, times)
    def open(self, path, flags):
        #print "xmp.py:Xmp:open: %s" % path
        os.close(os.open(path, flags))
        return 0

    def read(self, path, len, offset):
        #print "xmp.py:Xmp:read: %s" % path
        f = open(path, "r")
        f.seek(offset)
        return f.read(len)

    def write(self, path, buf, off):
        #print "xmp.py:Xmp:write: %s" % path
        f = open(path, "r+")
        f.seek(off)
        f.write(buf)
        return len(buf)

    def release(self, path, flags):
        print "xmp.py:Xmp:release: %s %s" % (path, flags)
        return 0
    def statfs(self):
        """
        Should return a tuple with the following 6 elements:
            - blocksize - size of file blocks, in bytes
            - totalblocks - total number of blocks in the filesystem
            - freeblocks - number of free blocks
            - totalfiles - total number of file inodes
            - freefiles - nunber of free file inodes

        Feel free to set any of the above values to 0, which tells
        the kernel that the info is not available.
        """
        print "xmp.py:Xmp:statfs: returning fictitious values"
        blocks_size = 1024
        blocks = 100000
        blocks_free = 25000
        files = 100000
        files_free = 60000
        namelen = 80
        return (blocks_size, blocks, blocks_free, files, files_free, namelen)
    def fsync(self, path, isfsyncfile):
        print "xmp.py:Xmp:fsync: path=%s, isfsyncfile=%s" % (path, isfsyncfile)
        return 0


if __name__ == '__main__':

    server = Xmp()
    server.flags = 0
    server.multithreaded = 1;
    server.main()


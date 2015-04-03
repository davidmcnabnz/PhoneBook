#!/usr/bin/env python
#@+leo-ver=4
#@+node:@file phonebookfs.py
#@@first

"""
Implements the 'PhoneBook' filesystem - a filesystem which 
rips off the 'deniable encryption' ideas of the rubberhose.org
project
"""
#@+others
#@+node:imports
# python standard imports

import sys, os, time, struct, StringIO, socket
from UserString import MutableString
import array
import traceback
import thread, threading
from errno import *
from stat import *

from code import InteractiveConsole

from base64 import encodestring as b64enc
from sha import new as sha1

# project-specific imports

from pbmodules.fuse import Fuse
from pbmodules import SSLCrypto

import pbconfig
import pbcmds
makedict = pbcmds.makedict
#@-node:imports
#@+node:globals
progname = sys.argv[0]

# constants for command pseudo-file states

CMD_IDLE = 0            # waiting for command
CMD_WRITING_CLOSED = 1  # command file created, writing
CMD_WRITING_DATA = 2    # command file created, writing
CMD_PENDING = 3         # have written command, waiting for client to getattr
CMD_READING_CLOSED = 4  # waiting for client to open
CMD_READING_DATA = 5    # client is currently reading back response

CMD_GETATTR = 0
CMD_READLINK = 1
CMD_GETDIR = 2
CMD_UNLINK = 3
CMD_RMDIR = 4
CMD_SYMLINK = 5
CMD_RENAME = 6
CMD_LINK = 7
CMD_CHMOD = 8
CMD_CHOWN = 9
CMD_TRUNCATE = 10
CMD_MKNOD = 11
CMD_MKDIR = 12
CMD_UTIME = 13
CMD_OPEN = 14
CMD_READ = 15
CMD_WRITE = 16
CMD_RELEASE = 17
CMD_FSYNC = 18

# this next command is internal-use-only
# ie, not a kernel command
CMD_FIND_INODE = 19


cmdnames = {CMD_GETATTR: 'getattr',
            CMD_READLINK: 'readlink',
            CMD_GETDIR: 'getdir',
            CMD_UNLINK: 'unlink',
            CMD_RMDIR: 'rmdir',
            CMD_SYMLINK: 'symlink',
            CMD_RENAME: 'rename',
            CMD_LINK: 'link',
            CMD_CHMOD: 'chmod',
            CMD_CHOWN: 'chown',
            CMD_TRUNCATE: 'truncate',
            CMD_MKNOD: 'mknod',
            CMD_MKDIR: 'mkdir',
            CMD_UTIME: 'utime',
            CMD_OPEN: 'open',
            CMD_READ: 'read',
            CMD_WRITE: 'write',
            CMD_RELEASE: 'release',
            CMD_FSYNC: 'fsync',
            CMD_FIND_INODE: 'findInode',
            }

# names of magic pseudo files/dirs

cmdFile = pbcmds.cmdFile[1:]   # for fs command interface, lop leading '/'
respFile = pbcmds.respFile[1:]   # for fs command interface, lop leading '/'
layerDir = pbcmds.layerDir     # for direct layer access, lop leading '/'

# store directory

storedir = "/tmp"

# hardwired filename lengths
filenamelength = 40

# precalc the size of the data portion of each content file
contentChunkSize = pbconfig.filesize - filenamelength

# biggest int-sized number for randomising times
biggestTime = int(2 ** 31 - 1)


# keep this disabled at all times, unless you really need it for debugging
ENABLE_DANGEROUS_PYCMD = 0

fuckup = 0
#@-node:globals
#@+node:class PhoneBookFs
class PhoneBookFs(Fuse):

    """
    Main class of the PhoneBook filesystem
    """
    #@	@+others
    #@+node:__init__
    def __init__(self, *args, **kw):
    
        #print "PhoneBookFs: args=%s" % repr(args)
        #print "PhoneBookFs: kw=%s" % repr(kw)
    
        Fuse.__init__(self)
    
        global storedir
        #print "kw = %s" % kw
        #print "optdict=%s" % self.optdict
        storedir = kw.get('storedir', self.optdict.get('storedir', None))
        self.storedir = storedir 
    
        # seed the prng
        global urandom
        urandom = open("/dev/urandom")
        seed = SSLCrypto.randomseed
        seed(str(time.time()))
        seed(urandom.read(256))
    
        # set all the store directory files to random dates
        try:
            for f in os.listdir(self.storedir):
                t = randomInt(biggestTime)
                os.utime(os.path.join(storedir, f), (t, t))
        except:
            # most likely cause of failure is mounting from readonly media (eg CDR)
            pass
    
        if kw.has_key('mountpoint'):
            self.mountpoint = kw['mountpoint']
     
        self.cmdState = CMD_IDLE
        self.cmdBuf = ""
    
        self.layers = {}
    
        self.openfiles = {}
    
        self.fs = self
    
        # launch fs manager thread
        thread.start_new_thread(self.threadCmd, ())
    
        # create an anonymous layermap
        self.map = LayerMap(self)
    
        if ENABLE_DANGEROUS_PYCMD:
            print "DANGER - python commands interface enabled"
            self.console = InteractiveConsole(globals())
    
        if 0:
            print "storedir: %s" % repr(self.storedir)
            print "mountpoint: %s" % repr(self.mountpoint)
            print "unnamed mount options: %s" % self.optlist
            print "named mount options: %s" % self.optdict
    
        if 'debug' in self.optlist:
            self.debug = 1
        else:
            self.debug = 0
    
        # do stuff to set up your filesystem here, if you want
        #thread.start_new_thread(self.mythread, ())
    
        global fs
        fs = self
    #@-node:__init__
    #@+node:attribs
    flags = 1
    
    #@-node:attribs
    #@+node:getattr
    def getattr(self, path):
        """
        Return the following in a tuple (or -1 if failed)
            #st_mode (protection bits)
            #st_ino (inode number)
            #st_dev (device)
            #st_nlink (number of hard links)
            #st_uid (user ID of owner)
            #st_gid (group ID of owner)
            #st_size (size of file, in bytes)
            #st_atime (time of most recent access)
            #st_mtime (time of most recent content modification)
            #st_ctime (time of most recent content modification or metadata change).
    
        """
        if self.debug:
            print "pbfs.getattr: %s" % path
    
        try:
            ret = self.handleCmd(CMD_GETATTR, path)
            #print "pbfs.getattr: got '%s'" % repr(ret)
            return ret
        except:
            if self.debug:
                traceback.print_exc()
            raise
    
    
    #@-node:getattr
    #@+node:readlink
    def readlink(self, path):
    
        if self.debug:
            print "pbfs.readlink: %s" % path
    
        return self.handleCmd(CMD_READLINK, path)
    
    
    
    #@-node:readlink
    #@+node:getdir
    def getdir(self, path):
    
        if self.debug:
            print "pbfs.getdir: %s" % path
    
        try:
            d = self.handleCmd(CMD_GETDIR, path)
            #print "pbfs.getdir: got '%s'" % repr(d)
            return d
        except:
            #traceback.print_exc()
            raise
    
    
    
    #@-node:getdir
    #@+node:unlink
    def unlink(self, path):
    
        if self.debug:
            print "pbfs.unlink: %s" % path
    
        return self.handleCmd(CMD_UNLINK, path)
    
    #@-node:unlink
    #@+node:rmdir
    def rmdir(self, path):
    
        if self.debug:
            print "pbfs.rmdir: %s" % path
    
        return self.handleCmd(CMD_RMDIR, path)
    
    #@-node:rmdir
    #@+node:link
    def link(self, path, path1):
    
        if self.debug:
            print "pbfs.link: %s %s" % (path, path1)
    
        # note a kludge here - reversing args, because 'path1'
        # will be the file we're creating, and 'path' is just the target
    
        return self.handleCmd(CMD_LINK, path1, path)
    #@-node:link
    #@+node:symlink
    def symlink(self, path, path1):
    
        if self.debug:
            print "pbfs.symlink: %s %s" % (path, path1)
    
        # note a kludge here - reversing args, because 'path1'
        # will be the file we're creating, and 'path' is just the target
    
        return self.handleCmd(CMD_SYMLINK, path1, path)
    #@-node:symlink
    #@+node:rename
    def rename(self, path, path1):
    
        if self.debug:
            print "pbfs.rename: %s %s" % (path, path1)
    
        return self.handleCmd(CMD_RENAME, path, path1)
    #@-node:rename
    #@+node:chmod
    def chmod(self, path, mode):
    
        if self.debug:
            print "pbfs.chmod: %s %s" % (path, mode)
    
        return self.handleCmd(CMD_CHMOD, path, mode)
    #@-node:chmod
    #@+node:chown
    def chown(self, path, user, group):
    
        if self.debug:
            print "pbfs.chown: %s %s %s" % (path, user, group)
    
        return self.handleCmd(CMD_CHOWN, path, user, group)
    #@-node:chown
    #@+node:truncate
    def truncate(self, path, size):
    
        if self.debug:
            print "pbfs.truncate: %s %s" % (path, size)
    
        return self.handleCmd(CMD_TRUNCATE, path, size)
    #@-node:truncate
    #@+node:mknod
    def mknod(self, path, mode, dev):
    	""" Python has no os.mknod, so we can only do some things """
    
        if self.debug:
            print "pbfs.mknod: %s %s %s" % (path, mode, dev)
    
        return self.handleCmd(CMD_MKNOD, path, mode, dev)
    #@-node:mknod
    #@+node:mkdir
    def mkdir(self, path, mode):
    
        if self.debug:
            print "pbfs.mkdir: %s %s" % (path, mode)
    
        return self.handleCmd(CMD_MKDIR, path, mode)
    #@-node:mkdir
    #@+node:utime
    def utime(self, path, times):
    
        if self.debug:
            print "pbfs.utime: %s %s" % (path, times)
    
        return self.handleCmd(CMD_UTIME, path, times)
    #@-node:utime
    #@+node:open
    def open(self, path, flags):
    
        if self.debug:
            print "pbfs.open: %s %s" % (path, flags)
    
        return self.handleCmd(CMD_OPEN, path, flags)
    #@-node:open
    #@+node:read
    def read(self, path, len, offset):
    
        if self.debug:
            print "pbfs.read: %s %s %s" % (path, len, offset)
    
        return self.handleCmd(CMD_READ, path, len, offset)
    #@nonl
    #@-node:read
    #@+node:write
    def write(self, path, buf, offset):
    
        size = len(buf)
    
        if self.debug:
            print "pbfs.write: %s %s %s" % (path, offset, size)
    
        return self.handleCmd(CMD_WRITE, path, buf, offset)
    #@-node:write
    #@+node:release
    def release(self, path, flags):
    
        if self.debug:
            print "pbfs.release: %s %s" % (path, flags)
    
        return self.handleCmd(CMD_RELEASE, path, flags)
    #@-node:release
    #@+node:fsync
    def fsync(self, path, isfsyncfile):
    
        if self.debug:
            print "pbfs.fsync: path=%s, isfsyncfile=%s" % (path, isfsyncfile)
    
        return self.handleCmd(CMD_FSYNC, path, isfsyncfile)
    #@-node:fsync
    #@+node:statfs
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
    
        if self.debug:
            print "pbfs.statfs: returning fictitious values"
    
        blocks_size = 1024
        blocks = 100000
        blocks_free = 25000
        files = 100000
        files_free = 60000
        namelen = 80
    
        return (blocks_size, blocks, blocks_free, files, files_free, namelen)
    #@-node:statfs
    #@+node:findInode
    def findInode(self, path):
        """
        Retrieves the file object corresponding to 'path', or its parent
        if the full path doesn't exist.
        
        Spits an exception if neither full path nor parent dir exists.
        
        Arguments:
            - path - unix pathname string
        Returns:
            - tuple (fileobj, isparent):
                - fileobj - FileOrDir object corresponding to path (or parent)
                - isparent - 1 if we got the path's parent, 0 if we got path itself
        """
        return self.handleCmd(CMD_FIND_INODE, path)
    #@-node:findInode
    #@+node:handleCmd
    def handleCmd(self, cmd, path, *args):
        """
        All calls from kernel (except statfs) filter through to this method
        
        The purpose of this method is to:
            - intercept accesses to 'special filenames', and dispatch to handleFsCmd
            - intercept accesses to the '__layers' pseudo-directory, and dispatch
              to the specific layer
            - with remaining accesses, test the path arg against the current
              layermap's ruleset, and dispatch to the appropriate layer
        """
        # seed the prng
        seed = SSLCrypto.randomseed
        seed(str(time.time()))
        seed(urandom.read(64))
        seed(path)
    
        # break down the path
        pathbits = path.split("/")[1:]
    
        # intercept accesses to 'special filenames'
        if isspecial(pathbits):
            return self.handleFsCmd(cmd, pathbits, args)
    
        # flag indicating one or more layers are active
        gotlayers = (self.map and self.map.stack)
    
        # intercept accesses to root directory
        if path == '/':
            # operating on root dir
            if not self.map:
                raise PbOSError(ENOENT, "No layermap active")
            return self.map.handleCmd(cmd, [], args)
    
        # ---------------------------------
        # not the root - handle recursively
     
        # intercept accesses to special 'layers' pseudo-dir
        if pathbits[0] == layerDir:
            #print "PhoneBookFs: intercepting layer access, path=%s" % repr(pathbits)
    
            # trying to operate on layerdir itself?
            if len(pathbits) == 1:
                # yes - support some commands, barf at others
                if cmd == CMD_GETATTR:
                    # make up a dodgy stat record
                    now = int(time.time())
                    mode = S_IFDIR | S_IRUSR | S_IXUSR | S_IRGRP | S_IXGRP | S_IROTH | S_IXOTH
                    inode = dev = 0
                    nlink = 1
                    uid = gid = 0
                    size = 1024
                    atime = mtime = ctime = now
                    return (mode, inode, dev, nlink, uid, gid, size, atime, mtime, ctime)
                elif cmd == CMD_GETDIR:
                    if not gotlayers:
                        return [] # empty layers pseudo-dir
                    else:
                        s = self.map.stack
                        return [(l.name, 0) for l in s]
                else:
                    raise PbOSError(EACCES, "Permission Denied")
    
            # operating on direct subdir of layerdir?
            elif len(pathbits) == 2:
                layername = pathbits[1]
                if not gotlayers:
                    # barf if no layers
                    raise PbOSError(ENODEV, "No such layer '%s'" % layername)
    
                if cmd == CMD_GETATTR:
                    # fudge up a stat record
                    now = int(time.time())
                    mode = S_IFDIR | S_IRUSR | S_IXUSR | S_IRGRP | S_IXGRP | S_IROTH | S_IXOTH
                    inode = 0
                    #dev = 0
                    layerhash = hash(layername)
                    #print repr(layerhash)
                    dev = int(("0x%s" % layerhash[:7]), 16)
                    #print "Faking dev=%s" % dev
                    nlink = 1
                    uid = gid = 0
                    size = 1024
                    atime = mtime = ctime = now
                    return (mode, inode, dev, nlink, uid, gid, size, atime, mtime, ctime)
    
                elif cmd != CMD_GETDIR:
                #else:
                    # barf if any other command other than getdir
                    raise PbOSError(ENODEV, "No such layer '%s'" % layername)
    
            #print "FORWARDING TO LAYER"
    
            # create path with layerdir stripped out
            layername = pathbits[1] # extract the layer name
            layerpathbits = pathbits[2:]
            #print "FORWARDING TO LAYER1"
            try:
                #print "FORWARDING TO LAYER2"
                layer = self.map.layernames[layername]
            except:
                traceback.print_exc()
                print "Existing layers: %s" % repr(self.map.layernames.keys())
                print "FORWARDING TO LAYER3"
                raise PbOSError(ENODEV, "No such layer '%s'" % layername)
    
            # got a valid layer - pass in the command
            ret = layer.handleCmd(cmd, layerpathbits, args)
            return ret
    
        # here, we must have an active layermap - barf if not
        if not self.map:
            raise PbOSError(ENODEV, "No layermap active")
    
        # normal access - send to layermap
        if pathbits == ['']:
            pathbits = []
        #print "PhoneBookFs: pathbits='%s'" % repr(pathbits)
        return self.map.handleCmd(cmd, pathbits, args)
    
    
    #@-node:handleCmd
    #@+node:handleFsCmd
    def handleFsCmd(self, cmd, pathbits, args):
        """
        Handles all accesses to the command pseudofile
        
        Implemented here as a hardwired state machine
        
        Rather grotty - best if you look at execCmd instead - it'll make more sense
        """
        state = self.cmdState
    
        #print "handleCmd: state=%s, cmd=%s" % (self.cmdState, cmd)
    
        if state == CMD_IDLE:       # waiting for command
            if cmd == CMD_GETATTR:
                # make out that the file doesn't exist
                raise PbOSError(ENOENT, "No such file or directory '%s'" % repr(pathbits))
            elif cmd == CMD_MKNOD:
                # start of command input
                self.cmdState = CMD_WRITING_CLOSED
                self.cmdMode = args[0] # the 'mode' arg
                return 0
            elif cmd == CMD_OPEN:
                mode = args[0] & 3
                if mode == 0:
                    raise PbOSError(EPERM, "Illegal operation")
                elif mode in [1,2]:
                    self.cmdState = CMD_WRITING_DATA
                    return 0
                else:
                    raise PbOSError(EPERM, "Illegal operation")
            elif cmd == CMD_READ:
                raise PbOSError(EPERM, "Illegal operation")
            elif cmd == CMD_WRITE:
                raise PbOSError(EPERM, "Illegal operation")
            elif cmd == CMD_RELEASE:
                raise PbOSError(EPERM, "Illegal operation")
            elif cmd == CMD_FSYNC:
                return 0
            elif cmd == CMD_TRUNCATE:
                return 0
            elif cmd in [CMD_GETDIR, CMD_UNLINK, CMD_RMDIR, CMD_SYMLINK, CMD_READLINK,
                         CMD_RENAME, CMD_LINK, CMD_CHMOD, CMD_CHOWN,
                         CMD_MKDIR, CMD_UTIME]:
                # none of these are valid for the command file
                raise PbOSError(EPERM, "Illegal operation")
            raise PbOSError(EPERM, "Illegal operation")
    
        elif state == CMD_WRITING_CLOSED:  # waiting for client to open for writing
            if cmd == CMD_GETATTR:
                # mode,ino,dev,nlink,uid,gid,size,atime,mtime,ctime,
                now = long(time.time())
                stat = (self.cmdMode, 0L, 0L, 1, 0, 0, 0, now, now, now)
                return stat
    
            elif cmd == CMD_MKNOD:
                raise PbOSError(EPERM, "Illegal operation")
            elif cmd == CMD_OPEN:
                mode = args[0] & 3
                if mode == 0:
                    raise PbOSError(EPERM, "Illegal operation")
                elif mode in [1,2]:
                    self.cmdState = CMD_WRITING_DATA
                    return 0
                else:
                    raise PbOSError(EPERM, "Illegal operation")
            elif cmd == CMD_READ:
                raise PbOSError(EPERM, "Illegal operation")
            elif cmd == CMD_WRITE:
                raise PbOSError(EPERM, "Illegal operation")
            elif cmd == CMD_RELEASE:
                raise PbOSError(EPERM, "Illegal operation")
            elif cmd == CMD_FSYNC:
                return 0
            elif cmd == CMD_TRUNCATE:
                return 0
            elif cmd in [CMD_GETDIR, CMD_UNLINK, CMD_RMDIR, CMD_SYMLINK, CMD_READLINK,
                         CMD_RENAME, CMD_LINK, CMD_CHMOD, CMD_CHOWN,
                         CMD_MKDIR, CMD_UTIME]:
                # none of these are valid for the command file
                raise PbOSError(EPERM, "Illegal operation")
            raise PbOSError(EPERM, "Illegal operation")
    
        elif state == CMD_WRITING_DATA:  # command file opened, now writing
            if cmd == CMD_GETATTR:
                now = long(time.time())
                stat = (self.cmdMode, 0L, 0L, 1, len(self.cmdBuf), 0, 0, now, now, now)
                return stat
                # mode,ino,dev,nlink,uid,gid,size,atime,mtime,ctime,
            elif cmd == CMD_MKNOD:
                raise PbOSError(EPERM, "Illegal operation")
            elif cmd == CMD_OPEN:
                raise PbOSError(EPERM, "Illegal operation")
            elif cmd == CMD_READ:
                raise PbOSError(EPERM, "Illegal operation")
            elif cmd == CMD_WRITE:
                buf, offset = args
                self.cmdBuf += buf
                return len(buf)
    
            elif cmd == CMD_RELEASE:
                # -------------------------------
                # we finally get to execute the command
                try:
                    self.cmdResp = self.execCmd(self.cmdBuf)
                    #print "handleCmd: result='%s'" % repr(self.cmdResp)
                except:
                    traceback.print_exc()
                self.cmdBuf = ""
                now = long(time.time())
                # mode,ino,dev,nlink,uid,gid,size,atime,mtime,ctime,
                self.cmdStat = (33279, 0L, 0L, 1, 0, 0, len(self.cmdResp), now, now, now)
    
                # now waiting for client to pick it up
                self.cmdState = CMD_PENDING
                return 0
    
            elif cmd == CMD_FSYNC:
                return 0
            elif cmd == CMD_TRUNCATE:
                return 0
            elif cmd in [CMD_GETDIR, CMD_UNLINK, CMD_RMDIR, CMD_SYMLINK, CMD_READLINK,
                         CMD_RENAME, CMD_LINK, CMD_CHMOD, CMD_CHOWN,
                         CMD_MKDIR, CMD_UTIME]:
                # none of these are valid for the command file
                raise PbOSError(EPERM, "Illegal operation")
            raise PbOSError(EPERM, "Illegal operation")
    
        elif state == CMD_PENDING:  # have written command, waiting for client to retrieve response
            if cmd == CMD_GETATTR:
                self.cmdState = CMD_READING_CLOSED
                return self.cmdStat
            elif cmd == CMD_MKNOD:
                raise PbOSError(EPERM, "Illegal operation")
            elif cmd == CMD_OPEN:
                mode = args[0] & 3
                if mode != 0:
                    raise PbOSError(EPERM, "Illegal operation")
                self.cmdState = CMD_READING_DATA
                return 0
            elif cmd == CMD_READ:
                raise PbOSError(EPERM, "Illegal operation")
            elif cmd == CMD_WRITE:
                raise PbOSError(EPERM, "Illegal operation")
            elif cmd == CMD_RELEASE:
                raise PbOSError(EPERM, "Illegal operation")
            elif cmd == CMD_FSYNC:
                raise PbOSError(EPERM, "Illegal operation")
            elif cmd == CMD_TRUNCATE:
                return 0
            elif cmd in [CMD_GETDIR, CMD_UNLINK, CMD_RMDIR, CMD_SYMLINK, CMD_READLINK,
                         CMD_RENAME, CMD_LINK, CMD_CHMOD, CMD_CHOWN,
                         CMD_MKDIR, CMD_UTIME]:
                # none of these are valid for the command file
                raise PbOSError(EPERM, "Illegal operation")
            raise PbOSError(EPERM, "Illegal operation")
    
        elif state == CMD_READING_CLOSED:  # client has stated response, yet to open
            if cmd == CMD_GETATTR:
                return self.cmdStat
            elif cmd == CMD_MKNOD:
                raise PbOSError(EPERM, "Illegal operation")
            elif cmd == CMD_OPEN:
                mode = args[0] & 3
                if mode != 0:
                    raise PbOSError(EPERM, "Illegal operation")
                self.cmdState = CMD_READING_DATA
                return 0
    
            elif cmd == CMD_READ:
                raise PbOSError(EPERM, "Illegal operation")
            elif cmd == CMD_WRITE:
                raise PbOSError(EPERM, "Illegal operation")
            elif cmd == CMD_RELEASE:
                raise PbOSError(EPERM, "Illegal operation")
            elif cmd == CMD_FSYNC:
                raise PbOSError(EPERM, "Illegal operation")
            elif cmd == CMD_TRUNCATE:
                return 0
            elif cmd in [CMD_GETDIR, CMD_UNLINK, CMD_RMDIR, CMD_SYMLINK, CMD_READLINK,
                         CMD_RENAME, CMD_LINK, CMD_CHMOD, CMD_CHOWN,
                         CMD_MKDIR, CMD_UTIME]:
                # none of these are valid for the command file
                raise PbOSError(EPERM, "Illegal operation")
            raise PbOSError(EPERM, "Illegal operation")
    
        elif state == CMD_READING_DATA:  # client is currently reading back response
            if cmd == CMD_GETATTR:
                return self.cmdStat
            elif cmd == CMD_MKNOD:
                raise PbOSError(EPERM, "Illegal operation")
            elif cmd == CMD_OPEN:
                raise PbOSError(EPERM, "Illegal operation")
            elif cmd == CMD_READ:
                nbytes, offset = args
                #print "handleFsCmd: reading response '%s'" % repr(self.cmdResp)
                buf = self.cmdResp[0:nbytes]
                #print "handleCmd:read: %s %s %s '%s'" % (path, nbytes, offset, buf)
                self.respBuf = self.cmdResp[nbytes:]
                return buf
                
            elif cmd == CMD_WRITE:
                raise PbOSError(EPERM, "Illegal operation")
            elif cmd == CMD_RELEASE:
                self.cmdState = CMD_IDLE
                return 0
            elif cmd == CMD_FSYNC:
                return 0
            elif cmd == CMD_TRUNCATE:
                return 0
            elif cmd in [CMD_GETDIR, CMD_UNLINK, CMD_RMDIR, CMD_SYMLINK, CMD_READLINK,
                         CMD_RENAME, CMD_LINK, CMD_CHMOD, CMD_CHOWN,
                         CMD_MKDIR, CMD_UTIME]:
                # none of these are valid for the command file
                raise PbOSError(EPERM, "Illegal operation")
            raise PbOSError(EPERM, "Illegal operation")
    
    
    
    
    #@-node:handleFsCmd
    #@+node:execCmd
    def execCmd(self, cmd):
        """
        Executes a command 'file', and returns response
        
        Argument:
            - raw string, formatted properly as a command
        Returns:
            - raw string, formatted properly as a response
        """
    
        # parse raw input into a python dict
        try:
            d = pbcmds.decodeDict(cmd)
        except:
            return pbcmds.encodeDict(None, "PBResp",
                                     status="error", detail="Malformed buffer")
    
        #print "Got command dict: %s" % repr(d)
    
        # get required 'command' keyword, barf if absent
        cmd = d.get('command', None)
        if not cmd:
            return pbcmds.encodeDict(None, "PBResp",
                                     status="error", detail="Missing command field")
    
        # now do command-specific processing
        meth = getattr(self, "cmd_"+cmd, None)
        if meth:
            return pbcmds.encodeDict(None, "PBResp", **meth(**d))
        else:
            return pbcmds.encodeDict(None, "PBResp",
                                     status="error", detail="Unknown command '%s'" % cmd)
    
    
    
    #@-node:execCmd
    #@+node:cmd_hello
    def cmd_hello(self, **kw):
        return makedict(status="success", detail="Hello to you too")
    
    #@-node:cmd_hello
    #@+node:cmd_openmap
    def cmd_openmap(self, **kw):
        """
        Opens an existing layermap, and switches to using this layermap
        
        Keywords:
            - name - text name of layermap
            - passphrase - layer passphrase
        """
        try:
            name = kw['name']
        except:
            return makedict(status="error",
                        detail="openmap: missing name")
        try:
            passphrase = kw['passphrase']
        except:
            return makedict(status="error",
                        detail="openmap: missing passphrase")
    
        try:
            layermap = LayerMap(self, name, passphrase)
        except:
            traceback.print_exc()
            return makedict(status="error",
                        detail="openmap: failed to create layermap object")
    
        # success
        self.map = layermap
        return makedict(status="success", detail="now using layermap '%s'" % name)
    
    
    
    
    #@-node:cmd_openmap
    #@+node:cmd_destroymap
    def cmd_destroymap(self, **kw):
        """
        destroys an existing layermap
        
        Keywords:
            - name - text name of layermap
            - passphrase - layer passphrase
        """
        try:
            name = kw['name']
        except:
            return makedict(status="error",
                        detail="destroymap: missing name")
        try:
            passphrase = kw['passphrase']
        except:
            return makedict(status="error",
                        detail="destroymap: missing passphrase")
    
        if self.map.name == name:
            # create an anonymous layermap
            self.map = LayerMap(self)
    
        try:
            layermap = LayerMap(self, name, passphrase, destroy=1)
        except:
            traceback.print_exc()
            return makedict(status="error",
                        detail="destroymap: failed to destroy layermap object")
    
        # success
        return makedict(status="success", detail="destroyed layermap '%s' (if it ever existed, that is)" % name)
    
    #@-node:cmd_destroymap
    #@+node:cmd_newmap
    def cmd_newmap(self, **kw):
        """
        Creates a layermap, and switches to using this layermap
        Complains if trying to overwrite existing map
        
        Keywords:
            - name - text name of layermap
            - passphrase - layer passphrase
        """
        try:
            name = kw['name']
        except:
            return makedict(status="error",
                        detail="newmap: missing name")
        try:
            passphrase = kw['passphrase']
        except:
            return makedict(status="error",
                        detail="newmap: missing passphrase")
    
        try:
            layermap = LayerMap(self, name, passphrase)
        except:
            return makedict(status="error",
                        detail="openmap: failed to create layermap object")
        
        # barf if the map file already exists
        if os.path.isfile(layermap.pathname):
            return makedict(status="error",
                        detail="newmap: layermap '%s' already exists")
    
        # try to create the layermap
        try:
            layermap.new()
        except:
            return makedict(status="error",
                        detail="newmap: create failed")
    
        # success
        self.map = layermap
        return makedict(status="success", detail="now using new layermap '%s'" % name)
    
    #@-node:cmd_newmap
    #@+node:cmd_clonemapto
    def cmd_clonemapto(self, **kw):
        """
        Makes a copy of the current layermap to a new
        name/passphrase
        
        Keywords:
            - name - name to clone the new map as
            - passphrase - passphrase for securing new map
        """
        # sanity check - barf if no current map is active
        if not self.map:
            return makedict(status="error",
                        detail="clonemap: you must open an existing map first")
        
        # get parameters
        try:
            name = kw['name']
        except:
            return makedict(status="error",
                        detail="clonemap: missing name")
        try:
            passphrase = kw['passphrase']
        except:
            return makedict(status="error",
                        detail="clonemap: missing passphrase")
    
        try:
            ret = self.map.cloneto(name, passphrase)
        except:
            ret = None
        if isinstance(ret, LayerMap):
            return makedict(status="success",
                        detail="cloned current layermap to new map %s" % name)
    #@-node:cmd_clonemapto
    #@+node:cmd_createlayer
    def cmd_createlayer(self, **kw):
        """
        Creates a whole new layer, but does not add it to the current layermap
        
        Keywords:
            - name - name of layer
            - passphrase - layer's passphrase
        
        Note:
            - you can freely create a layer with the same name as an existing
              layer, but a different passphrase. this will make a completely
              distinct layer
        """
        try:
            name = kw['name']
        except:
            return makedict(status="error",
                        detail="createlayer: missing name")
        try:
            passphrase = kw['passphrase']
        except:
            return makedict(status="error",
                        detail="createlayer: missing passphrase")
    
        layer = FsLayer(self, name, passphrase)
    #@-node:cmd_createlayer
    #@+node:cmd_addlayer
    def cmd_addlayer(self, **kw):
        """
        Appends a new layer to the bottom of the current layermap stack
        
        Keywords:
            - name - name of layer
            - passphrase - layer's passphrase
        
        Note:
            - you can freely create a layer with the same name as an existing
              layer, but a different passphrase. this will make a completely
              distinct layer
        """
        try:
            name = kw['name']
        except:
            return makedict(status="error",
                        detail="addlayer: missing name")
        try:
            passphrase = kw['passphrase']
        except:
            return makedict(status="error",
                        detail="addlayer: missing passphrase")
    
        if name in self.map.layernames.keys():
            return makedict(status="error",
                        detail=("addlayer: map already has a layer called '%s'" % name),
                        )
    
        try:
            self.map.addlayer(name, passphrase)
            return makedict(status="success",
                        detail="addlayer: new layer '%s' successfully appended" % name)
        except:
            traceback.print_exc()
            return makedict(status="error",
                        detail="addlayer: failed to create layer '%s'" % name)
    #@-node:cmd_addlayer
    #@+node:cmd_pushlayer
    def cmd_pushlayer(self, **kw):
        """
        Pushes a new layer to the top of the current layermap stack
        
        Keywords:
            - name - name of layer
            - passphrase - layer's passphrase
        
        Note:
            - you can freely create a layer with the same name as an existing
              layer, but a different passphrase. this will make a completely
              distinct layer
        """
        try:
            name = kw['name']
        except:
            return makedict(status="error",
                        detail="pushlayer: missing name")
        try:
            passphrase = kw['passphrase']
        except:
            return makedict(status="error",
                        detail="pushlayer: missing passphrase")
    
        if name in self.map.layernames.keys():
            return makedict(status="error",
                        detail=("pushlayer: map already has a layer called '%s'" % name),
                        )
    
        try:
            self.map.pushlayer(name, passphrase)
            return makedict(status="success",
                        detail="pushlayer: new layer '%s' successfully pushed" % name)
        except:
            traceback.print_exc()
            return makedict(status="error",
                        detail="pushlayer: failed to create layer '%s'" % name)
    #@-node:cmd_pushlayer
    #@+node:cmd_poplayer
    def cmd_poplayer(self, **kw):
        """
        Pops a layer from the top of the active layermap
        """
        if self.map.name is None:
            mapname = ''
        else:
            mapname = self.map.name
    
        if len(self.map.stack) == 0:
            return makedict(status="error",
                        detail="active layermap '%s' currently empty" % mapname,
                        mapname=mapname,
                        )
    
        try:
            name = self.map.stack[0].name
            self.map.poplayer()
            return makedict(status="success",
                        detail="poplayer: layer '%s' removed from top of stack" % name)
        except:
            
            return makedict(status="error",
                        detail="poplayer: failed to pop layer '%s'" % name)
    
    
    #@-node:cmd_poplayer
    #@+node:cmd_droplayer
    def cmd_droplayer(self, **kw):
        """
        drops the named layer from the current layermap
        """
        try:
            name = kw['name']
        except:
            return makedict(status="error",
                        detail="droplayer: missing name")
    
        try:
            self.map.droplayer(name)
            return makedict(status="success",
                        detail="droplayer: layer '%s' removed" % name)
        except:
            #traceback.print_exc()
            #print "cmd_droplayer failed"
            return makedict(status="error",
                        detail="droplayer: failed to remove layer '%s'" % name)
    
    #@-node:cmd_droplayer
    #@+node:cmd_purgelayer
    def cmd_purgelayer(self, **kw):
        """
        Eliminates all files comprising layer 'layername'
        from the filesystem. Deletes the layer from the store
        """
    #@-node:cmd_purgelayer
    #@+node:cmd_listmap
    def cmd_listmap(self, **kw):
        """
        Returns a list of the currently active layermap's layers
        """
        if self.map.name is None:
            mapname = ''
        else:
            mapname = self.map.name
    
        #if mapname == '':
        #    return makedict(status="success",
        #                detail="no layermap active",
        #                mapname='',
        #                )
        
        if len(self.map.stack) == 0:
            return makedict(status="success",
                        detail="active layermap '%s' currently empty" % mapname,
                        mapname=mapname,
                        layers='',
                        )
    
        layers = "/".join([layer.name for layer in self.map.stack])
        return makedict(status="success",
                    detail="Layer map listing follows",
                    mapname=mapname,
                    layers=layers,
                    )
    #@-node:cmd_listmap
    #@+node:cmd_makechaff
    def cmd_makechaff(self, **kw):
        """
        Generates a specified quantity of 'chaff' in the datastore
        
        Keywords:
            - size - an int or string indicating size:
                - if int, generates that number of bytes, rounded up to
                  size of datastore files
                - if string, gets converted to int:
                    - if ends with 'k', 'm' or 'g' (case-insensitive), multiplies the int
                      portion by 1024, 1024**2 or 1024**3, for Kilobytes, Megabytes or Gigabytes
              for example:
                  - 65536 - 64k
                  - 32k   - 32768
                  - 3M    - 3145728
        """
        try:
            size = kw['size']
        except:
            return makedict(status="error",
                        detail="makechaff: missing size")
    
        # process 'size' arg
        if type(size) not in [type(0), type(0L), type('')]:
            return makedict(status='error',
                            detail='makechaff: size must be int, long or string, got %s' % repr(size))
        if type(size) == type(''):
            if size == '':
                return makedict(status='error',
                                detail='makechaff: size is an empty string!')
            last = size[-1].lower()
            multipliers = {'k':1024L, 'm':1024L**2, 'g':1024L**3, 't':1024L**4}
            if last in multipliers.keys():
                try:
                    size = long(size[:-1]) * multipliers[last]
                except:
                    return makedict(status='error',
                                    detail='makechaff: invalid size specifier %s' % repr(size))
            elif last.isdigit():
                size = long(size)
            else:
                return makedict(status='error',
                                detail='makechaff: size arg %s has invalid suffix' % repr(size))
        else:
            size = long(size)
    
        # round up to filesize
        gran = pbconfig.filesize
        nfiles = (size + gran - 1) / gran
        size = nfiles * gran
    
        # now generate the chaff files
        i = 0
        while i < nfiles:
            # get the random filename
            name = randomFilename()
    
            # and randomise its date
            t = randomInt(biggestTime)
            os.utime(os.path.join(storedir, name), (t, t))
    
            i += 1
    
        return makedict(status="success",
                    detail="makechaff: added %s bytes of chaff to datastore" % size)
    #@-node:cmd_makechaff
    #@+node:cmd_pycmd
    def cmd_pycmd(self, **kw):
        """
        This is a dangerous method that should be disabled
        """
        if not ENABLE_DANGEROUS_PYCMD:
            return makedict(status="error",
                        detail="Unknown command 'pycmd'")
    
        # retrieve and unpack command text
        oldstdout = sys.stdout
        oldstderr = sys.stderr
        s = StringIO.StringIO()
        sys.stdout = s
        sys.stderr = s
        try:
            cmd = kw.get('pycmd', '')
            cont = int(self.console.push(cmd))
        except:
            traceback.print_exc(file=s)
            print "got err"
            cont = 0
        sys.stdout = oldstdout
        sys.stderr = oldstderr
    
        #print "executed python command"
        return makedict(status="success",
                    detail="command executed",
                    output=s.getvalue(),
                    cont=cont)
    
    #@-node:cmd_pycmd
    #@+node:threadCmd
    def threadCmd(self):
        """
        Thread which listens for command connections on the unix socket,
        and executes these
        """
        #print "threadCmd: started"
        try:
            # create unix socket for command connections
            self.cmdFile = os.path.join("/tmp", "pbfs."+(self.mountpoint.replace("/", "_")))
            try:
                os.unlink(self.cmdFile)
            except:
                pass
            s = self.cmdsock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        
            # try to bind, until the exceptions stop
            #print "threadCmd: awaiting cmd conns on unix socket %s" % self.cmdsock.getsockname()
            while 1:
                try:
                    s.bind(self.cmdFile)
                    break
                except:
                    print "phonebook: waiting a bit to retry cmd sock bind"
                    time.sleep(10)
            s.listen(1)
        
            # now loop, accepting connections, getting/executing commands, sending replies
            while 1:
                conn, addr = s.accept()
                data = conn.recv(1024)
                try:
                    resp = self.execCmd(data)
                    #print "handleCmd: result='%s'" % repr(resp)
                    conn.send(resp)
                    conn.close()
                except:
                    traceback.print_exc()
        except:
            traceback.print_exc()
            print "socket thread has died"    
    #@-node:threadCmd
    #@+node:mythread
    def mythread(self):
    
        """
        The beauty of the FUSE python implementation is that with the python interp
        running in foreground, you can have threads
        """    
        print "mythread: started"
        #while 1:
        #    time.sleep(120)
        #    print "mythread: ticking"
    
    #@-node:mythread
    #@-others
#@-node:class PhoneBookFs
#@+node:class LayerMap
class LayerMap(Fuse):
    """
    Implements a layer map (ie, an ordered stack of FsLayer objects,
    plus a set of rules for routing kernel reqs to the appropriate layer
    """
    #@    @+others
    #@+node:__init__
    def __init__(self, parent, name=None, passphrase=None, **kw):
        """
        Creates a filesystem layermap object
    
        Arguments:
            - parent - ref to either main PhoneBookFs object, or parent layer object
            - name - text name of the layer (optional)
            - passphrase - text passphrase (optional)
        
        Keywords:
            - destroy - default 0 - if 1, destroys the map instead of opening/creating
    
        Note that if name and passphrase are not given, the layermap will not
        be able to save to disk (as is the case with the empty layermap created
        when the FS starts up).
        """
        # store parameters
        self.parent = parent
        self.fs = parent.fs
        self.storedir = storedir = parent.storedir
    
        #print "LayerMap init: name=%s passphrase=%s" % (repr(name), repr(passphrase))
    
        # initial empty layer stack
        self.stack = []
        self.layernames = {}
    
        # initial null rule-set
        self.rules = []
    
        # if name/pass supplied, set up new names and crypto
        if name and passphrase:
            # remember layermap's new id
            self.name = name
            self.passphrase = passphrase
    
            # determine the name of the layermap file
            self.filename = filename = hash(name+":"+passphrase)
            self.pathname = pathname = os.path.join(storedir, filename)
    
            # hari-kiri if indicated
            if kw.get('destroy', 0):
                self.destroy()
                return
            
            # determine an IV - use the first 8 bytes of binary hash of name+passwd
            iv = self.iv = sha1(name+":"+passphrase+":"+filename).digest()[0:8]
    
            #print "LayerMap.__init__: name=%s, pass=%s, iv=%s" % (repr(name), repr(passphrase), repr(iv))
    
            # create symmetrical encryption object
            self.cipher = SSLCrypto.blowfish(passphrase, iv)
        
            self.hasfile = 1
    
            # load if there is already a file
            if self.exists():
                self.load()
            else:
                self.save()
        else:
            self.name = None
            self.hasfile = 0
    
        #print "LayerMap init: done"
    
    
    
    #@-node:__init__
    #@+node:setAccess
    def setAccess(self, name=None, passphrase=None):
        """
        Sets the name and passphrase for this layermap
        
        Arguments:
            - name
            - passphrase
    
        Call with no arguments (or both none or empty) to make this a
        non-saving layer
        """
        # erase old file if it exists
        if self.hasfile:
            os.unlink(self.pathname)
    
        # if name/pass supplied, set up new names and crypto
        if name and passphrase:
            # remember layermap's new id
            self.name = name
            self.passphrase = passphrase
    
            # determine the name of the layermap file
            self.filename = filename = hash(name+":"+passphrase)
            self.pathname = pathname = os.path.join(storedir, filename)
            
            # determine an IV - use the first 8 bytes of binary hash of name+passwd
            iv = self.iv = sha1(name+":"+passphrase+":"+filename).digest()[0:8]
            
            # create symmetrical encryption object
            self.cipher = SSLCrypto.blowfish(passphrase, iv)
        
            self.hasfile = 1
            self.save()
        else:
            # mark this as a non-savable layer
            self.hasfile = 0
    
    #@-node:setAccess
    #@+node:load
    def load(self):
        """
        Loads a layermap from file
    
        format of file's plaintext is:
            - layer-decs
            - two newlines
            - rule-decs
            - two-newlines
            - chaff
    
        Format of layer-decs is:
            - layername:passphrase<newline>
            - ...
        
        Format of rule-decs is:
            - op:mask:layername<newline>
            - ...
        """
        if not self.hasfile:
            print "LayerMap.load: cannot load, no file parms"
            return
    
        #print "LayerMap.load: trying to load from %s" % self.pathname
    
        #print "LayerMap.__init__: name=%s, pass=%s, iv=%s" % (repr(name), repr(passphrase), repr(iv))
    
        # read in ciphertext
        f = file(self.pathname, "rb")
        raw_enc = f.read()
        #print "Layermap.load: file ciphertext hash=%s" % hash(raw_enc)
        f.close()
        
        # decrypt it
        self.cipher.setIV(self.iv)
        raw_plain = self.cipher.decrypt(raw_enc)
    
        #print "LayerMap.load: raw = '%s'" % repr(raw_plain[:50])
    
        try:
            segments = raw_plain.split("\n\n")
            #print "LayerMap.load: got %s segments" % len(segments)
            #print repr(segments[0:2])
    
            nsegs = len(segments)
            if nsegs > 0:
                layers = segments[0]
            else:
                layers = ''
            if nsegs > 1:
                rules = segments[1]
            else:
                rules = ''
            del segments
            del nsegs
        except:
            layers = raw_plain
            rules = ''
    
        layerlines = layers.split("\n")
    
        # initial empty layer stack
        self.stack = []
        self.layernames = {}
    
        for line in layerlines:
            if line == '':
                continue
            #print "*** line = %s" % repr(line[:50])
            name, passphrase = line.split(":", 1)
            layer = FsLayer(self, name, passphrase)
            self.stack.append(layer)
            self.layernames[name] = layer
    
        if rules:
            rulelines = rules.split("\n")
            for line in rulelines:
                try:
                    op, mask, layername = line.split(":")
                    self.rules.append((op, mask, layername))
                except:
                    traceback.print_exc()
                    print "dodgy rule line '%s'" % repr(line)
        
        #print "LayerMap.load: load from %s successful?" % self.pathname
    
    
    
    
    
    
    
    
    #@-node:load
    #@+node:save
    def save(self):
        """
        saves layermap to file
        """
        debug = self.fs.debug
        if not self.hasfile:
            if debug:
                print "LayerMap.save: cannot save, no file parms"
            return
    
        #print "LayerMap.save: trying to save to %s" % self.pathname
    
        # add layers:
        lines = []
        for layer in self.stack:
            lines.append("%s:%s" % (layer.name, layer.passphrase))
        #lines.append('')
    
        # add rules
        rules = []
        for rule in self.rules:
            line = "%s:%s:%s:" % (rule[0], rule[1], rule[2])
            #print "saving rule line '%s'" % repr(line)
            rules.append(line)
        #rules.append('')
    
        raw_plain = "\n".join(lines) + "\n\n" + "\n".join(rules) + "\n\n"
        
        #print "** raw_plain = %s" % repr(raw_plain)
    
        # add some chaff
        size = len(raw_plain)
        chaff = randomPadding(pbconfig.filesize - size)
        raw_plain += chaff
    
        # encrypt it    
        self.cipher.setIV(self.iv)
        raw_enc = self.cipher.encrypt(raw_plain)
    
        #print "Layermap.save: file ciphertext hash=%s" % hash(raw_enc)
    
        # and write it out
        try:
            #print "Layermap.save: pathname=%s" % self.pathname
            f = file(self.pathname, "wb")
            f.write(raw_enc)
            f.close()
        except:
            pass
    
        # and randomise the timestamp
        try:
            t = randomInt(biggestTime)
            os.utime(self.pathname, (t, t))
        except:
            pass
    
        # test the crypto
        #self.cipher.setIV(self.iv)
        #raw_dec = self.cipher.decrypt(raw_enc)
        #if raw_dec != raw_plain:
        #    print "Crypto failure saving layermap: orig %s, got %s" % (repr(raw_plain[:20]), repr(raw_dec[:20]))
        #else:
        #    print "crypto verify of layermap ok"
        self.load()
    
    
    #@-node:save
    #@+node:destroy
    def destroy(self):
        if not self.exists():
            return
        
        try:
            os.unlink(self.pathname)
        except:
            pass
    
        
    
    #@-node:destroy
    #@+node:addlayer
    def addlayer(self, layername, passphrase):
        """
        Appends another layer to the bottom of this layermap's stack
        """
        debug = self.fs.debug
        if debug:
            print "LayerMap.addlayer: appending new layer %s" % layername
        newlayer = FsLayer(self, layername, passphrase)
        self.stack.append(newlayer)
        self.layernames[layername] = newlayer
        self.save()
        if debug:
            print "LayerMap.pushlayer: done"
    #@-node:addlayer
    #@+node:pushlayer
    def pushlayer(self, layername, passphrase):
        """
        Pushes another layer to the top of this layermap's stack
        """
        print "LayerMap.pushlayer: pushing new layer %s" % layername
        newlayer = FsLayer(self, layername, passphrase)
        self.stack.insert(0, newlayer)
        self.layernames[layername] = newlayer
        self.save()
        #print "LayerMap.pushlayer: done"
    
    #@-node:pushlayer
    #@+node:poplayer
    def poplayer(self):
        """
        pops a layer from the top of the layer stack
        """
        if len(self.stack) == 0:
            print "poplayer: stack is empty!!"
            return
    
        print "poplayer: popping layer %s" % self.stack[0].name
        layer = self.stack.pop(0)
        del self.layernames[layer.name]
        self.save()
    #@-node:poplayer
    #@+node:droplayer
    def droplayer(self, layername):
        """
        drops a named layer from the layer stack
        """
        if layername not in self.layernames.keys():
            raise Exception("no layer '%s' currently in map")
    
        # find named layer
        layer = self.layernames[layername]
        del self.layernames[layername]
        self.stack.remove(layer)
        self.save()
    #@-node:droplayer
    #@+node:cloneto
    def cloneto(self, name, passphrase):
        """
        Clones this layermap to a new layermap, accessed by new
        name and passphrase
        """
        # try to create the layermap
        try:
            newmap = LayerMap(self.parent, name, passphrase)
        except:
            print "cloneto failed"
            traceback.print_exc()
            return makedict(status="error",
                        detail="clonemap: got exception")
        
        # barf if the map file already exists
        if os.path.isfile(newmap.pathname):
            return makedict(status="error",
                        detail="clonemap: layermap '%s' already exists")
    
        # now clone the properties of the current layermap
        newmap.stack[:] = self.stack[:]
        newmap.rules[:] = self.rules[:]
        newmap.layernames = makedict(self.layernames.items())
    
        # save the new map
        newmap.save()
    
        return makedict(status="success",
                    detail="clonemap: successfully cloned map to new map %s" % name)
    #@-node:cloneto
    #@+node:exists
    def exists(self):
        """
        Returns 1 if the layermap currently exists in the filesystem, or 0 if not
        """
        return os.path.isfile(self.pathname)
    #@-node:exists
    #@+node:handleCmd
    def handleCmd(self, cmd, pathbits, args):
        """
        Handle command from kernel within current layermap
        """
        #print "LayerMap '%s': cmd=%s path=%s" % (repr(self.name), cmdnames[cmd], repr(pathbits))
    
        # barf if layermap is empty
        if len(self.stack) == 0:
            raise PbOSError(ENODEV, "Layermap is empty")
    
        # -------------------------------------------------
        # intercept calls, and pass them to the right layer
        # -------------------------------------------------
    
        # reading a directory?
        if cmd == CMD_GETDIR:
            # yes - read the same dir on all layers, and amalgamate the results
            stackdirs = {}
            for layer in self.stack:
                try:
                    if self.fs.debug:
                        print "LayerMap: sending ggetdir to layer %s" % layer.name
                    tuples = layer.handleCmd(CMD_GETDIR, pathbits, args)
                    try:
                        d = makedict(tuples)
                    except:
                        traceback.print_exc()
                        print "shit1"
                        raise
                    stackdirs.update(makedict(tuples))
                    if self.fs.debug:
                        try:
                            print "LayerMap: fred getdir gives '%s' ('%s')" % (repr(tuples), repr(d))
                        except:
                            traceback.print_exc()
                            print "shit1"
                            raise
                except:
                    pass
            # by now, we have a dict where the entry names are keys, 0s are values
            if self.fs.debug:
                print "LayerMap: stackdirs='%s'" % repr(stackdirs)
            names = stackdirs.keys()
            names.sort()
            return [(name, 0) for name in names]
        
        # ------------------------------
        # Intercept operations on pre-existing files, pass them down to the first layer
        # which contains the file
        if cmd in [CMD_GETATTR, CMD_READLINK, CMD_RMDIR, CMD_RENAME,
                   CMD_CHMOD, CMD_CHOWN, CMD_LINK, CMD_UNLINK, CMD_SYMLINK,
                   CMD_TRUNCATE, CMD_UTIME, CMD_OPEN,
                   CMD_READ, CMD_FSYNC, CMD_READ, CMD_WRITE, CMD_RELEASE]:
            #print "*************"
            #print "intercepting for %s" % repr(pathbits)
            found = 0
            for layer in self.stack:
                try:
                    layer.handleCmd(CMD_GETATTR, pathbits, args)
                    found = 1
                    break
                except:
                    pass
            if found:
                return layer.handleCmd(cmd, pathbits, args)
    
        # -----------------------------------
        # intercept open for read
        if 0 and cmd == CMD_OPEN:
            flags = args[0]
            if not (flags and (os.O_WRONLY | os.O_RDWR | os.O_APPEND)):
                # opening readonly
                # find layer where the file exists
                found = 0
                for layer in self.stack:
                    try:
                        layer.handleCmd(CMD_GETATTR, pathbits, args)
                        found = 1
                        break
                    except:
                        pass
                if found:
                    return layer.handleCmd(CMD_OPEN, pathbits, args)
    
        
        # determine destination layer, based on ruleset
        try:
            layer = self.chooseTargetLayer(cmd, pathbits, args)
        except:
            traceback.print_exc()
            raise
    
        try:
            #print "LayerMap %s: choosing tgt layer %s" % (repr(self.name), layer.name)
            pass
        except:
            traceback.print_exc()
    
        # and dispatch to this layer
        ret = layer.handleCmd(cmd, pathbits, args)
    
        #print "LayerMap %s: command completed" % repr(self.name)
        return ret
    
    
    #@-node:handleCmd
    #@+node:chooseTargetLayer
    def chooseTargetLayer(self, cmd, path, args):
        """
        Go through our ruleset and determine which layer
        should handle this command
        """
        
        # temporary - just target everything at the first layer
        return self.stack[0]
    #@-node:chooseTargetLayer
    #@-others
#@-node:class LayerMap
#@+node:class FsLayer
class FsLayer(Fuse):
    """
    Implements a single layer in the filesystem

    As a class it's pretty thin - it just stores name and passphrase,
    which are used to generate the hashes for the contained inodes.

    Also, it keeps a set of refs to all currently opened inodes.
    This prevents the existence of duplicate references to the
    same inode, in cases where such inodes are hard-linked more than once.
    """
    #@    @+others
    #@+node:__init__
    def __init__(self, parent, name, passphrase, poolsize=65536, poolInodes=16):
        """
        Creates a filesystem layer object
        
        Arguments:
            - parent - ref to either main PhoneBookFs object, or parent layer object
            - name - text name of the layer
            - passphrase - text passphrase
            - poolsize - size of pool when creating layer
        """
        # store parameters
        self.parent = parent
        self.fs = parent.fs
        self.layer = self
        self.storedir = storedir = parent.storedir
        self.name = name
        self.passphrase = passphrase
        self.aspath = "/" # logical path relative to fs root, as seen by os
    
        self.inodes = {}  # layer-global store of all open inodes
    
        # get (or create) pool inode and pool inodes inode
        self.pool = Inode(self, 1, type='p', mode=0, poolsize=poolsize)
    
        # get (or create) root directory
        self.root = self.getInode(0, type="d", mode=0755)
    
    #@-node:__init__
    #@+node:getInode
    def getInode(self, inodenum=None, **kw):
        """
        Returns the inode object for inode inodenum, loading the inode
        from disk if it isn't yet loaded.
        """
        #print "getInode: inodenum = '%s'" % repr(inodenum)
        inode = self.inodes.get(inodenum, None)
        if inode is None:
            inode = Inode(self, inodenum, **kw)
            self.inodes[inode.inode] = inode
            #print "FsLayer.getInode: new inode# = '%s'" % inode.inode
        #else:
        #    print "Found inode '%s' ('%s')" % (inodenum, inode.inode)
        return inode
    
    #@-node:getInode
    #@+node:newInode
    def newInode(self, inodenum=None, **kw):
        """
        Creates a whole new inode
        """
        inode = Inode(self, inodenum, **kw)
        self.inodes[inode.inode] = inode
        return inode
    #@-node:newInode
    #@+node:handleCmd
    def handleCmd(self, cmd, pathbits, args):
        """
        Execute a kernel fs command in this layer
        
        This is where the real work happens.
        """
        #print "layer %s:%s:%s" % (self.name, cmdnames[cmd], repr(pathbits))
    
        return self.root.handleCmd(self, cmd, pathbits, args)
    #@-node:handleCmd
    #@-others
#@-node:class FsLayer
#@+node:class Inode
class Inode:
    """
    Manages each file/dir's inode
    
    The content files are actually a chain of blocks.
    
    Each block file has the format:
        - line - filename of next block, or NULL chars if this
          is the last block
        - data
    """
    #@	@+others
    #@+node:attribs
    fmt = "".join(["l",    # inode number
               "64s",  # filename of head content file
               "64s",  # content passphrase
               "8s",   # content iv
               "c",    # type - (d)irectory, (f)ile, (l)ink, (s)ymlink
               "x",    # pad1
               "h",    # nfiles (directory only)
    
               "l",    # mode
               "l",    # dev#
               "l",    # nlink - num hard links
               "l",    # uid
               "l",    # gid
               "l",    # size in bytes
               "l",    # atime - time of last access
               "l",    # mtime - time of last content modification
               "l",    # ctime - time of last content mod or metadata change
               ])
    #@-node:attribs
    #@+node:__init__
    def __init__(self, layer, inodenum=None, **kw):
        """
        Creates or loads a single inode.
        
        Arguments:
            - layer - FsLayer object, used for deriving hashed inode filename
            - inodenum - unique inode number (only if loading existing, otherwise None)
        
        Keywords (only if inodenum is None):
            - type - (d)irectory, (f)ile or (p)ool
            - mode - unix permissions mask
            - poolsize - only for mode=p, approximate size of files pool, one of:
                - nnnn - creates pool with nnnn bytes, rounded up to granularity
                - nnnnk - ditto, but creates nnnn kilobytes
                - nnnnm - ditto, but creates nnnn megabytes
                - nnnng - ditto, but creates nnnn gigabytes
        """
        # store parameters
        self.layer = layer
        self.fs = layer.fs
        self.storedir = storedir = layer.storedir
        self.lock = threading.Lock()
        self.numopen = 0    # number of instances of this inode being open
        self.openflags = 0
        
        self.image = ''
        self.imageChunkNames = [] # names of the files image chunks get written to
    
        # are we loading existing, or creating new?
        if inodenum == None:
            # create new inode
            self.type = kw['type']
            
            # loop around picking random inode numbers until we avoid a clash
            while 1:
                inodenum = randomNumber(31)
                s = "%s:%s:%s" % (layer.name, layer.passphrase, inodenum)
                ifile = hash(s)
                ipath = os.path.join(storedir, ifile)
                if not os.path.isfile(ipath):
                    # got a unique file
                    break
            self.ifile = ifile
            self.ipath = ipath
        else:
            s = "%s:%s:%s" % (layer.name, layer.passphrase, inodenum)
            ifile = self.ifile = hash(s)
            ipath = self.ipath = os.path.join(storedir, ifile)
    
        # create a deterministic inode passphrase and IV, and crypto object
        self.inode = inodenum
        ipass = self.ipass = sha1(s+s).hexdigest()
        iiv = self.iiv = sha1(s+s+s).digest()[0:8]
        icipher = self.icipher = SSLCrypto.blowfish(ipass, iiv)
    
        # attribs that are only relevant if this is a directory inode
        self.direntries = {} # dict - keys are entry names, values are inode objs
        self.dirisloaded = 0
    
        # load if exists, create if no
        if os.path.isfile(self.ipath):
            self.load()
        else:
            self.new(kw['type'], kw['mode'], kw.get('poolsize', '64k'))
    #@-node:__init__
    #@+node:new
    def new(self, itype, imode, pollsize=None):
        """
        Initialises and saves an inode
        
        Arguments:
            - itype - inode type - (d)irectory, (f)ile, (l)ink, (s)ymlink, (p)ool
            - imode - initial unix permissions mask
            - poolsize - only for itype=='p' - string specifying size of file pool
        """
    
        # generate a random content filename
        cfile = randomFilename()
        cpath = os.path.join(storedir, cfile)
    
        self.cfile = cfile
        self.imageChunkNames.append(self.cfile)
        self.cpath = cpath
    
        # generate random content file pass, iv
        cpass = self.cpass = randomPassphrase()
        civ = self.civ = randomIv()
        ccipher = self.ccipher = SSLCrypto.blowfish(cpass, civ)
    
        # write out a content file full of random padding
        #self.ccipher.setIV(self.civ)
        #f = file(self.cpath, "wb")
        #f.write(randomPadding(pbconfig.filesize))
        #f.close()
    
        self.type = itype
    
        # fill in other attribs
        self.nfiles = 0
        self.mode = imode
        self.dev = 0
        self.nlink = 0
        self.uid = os.getuid()
        self.gid = os.getgid()
        self.size = 0
        if self.type == 'd':
            self.mode |= S_IFDIR # add 'directory bit'
        elif self.type == 's':
            self.mode |= S_IFLNK
        now = int(time.time())
        self.atime = now
        self.mtime = now
        self.ctime = now
    
        #if self.type == 'p':
        #    # determine pool size
        #    self.generatePool(poolsize)
    
        self.save()
    
        if self.type == 'd':
            self.savedir()
    
    #@-node:new
    #@+node:save
        #else:
        #    # load an existing inode, creating a new one if it doesn't exist
        #    s = "%s:%s:%s" % (layer.name, layer.passphrase, inodenum)
        #
        #    # create a deterministic inode passphrase and IV, and crypto object
        #    ipass = self.ipass = sha1(s+s).hexdigest()
        #    iiv = self.iiv = sha1(s+s+s).digest()[0:8]
        #    icipher = self.icipher = SSLCrypto.blowfish(ipass, iiv)
        #
        #    # load from file
        #    ifile = self.ifile = hash(s)
        #    ipath = self.ipath = os.path.join(storedir, ifile)
        #    # do the loading here...
    
        ## determine the name of the layer file
        #s = "%s:%s:%s" % (layer.name, layer.passphrase, inodenum)
    
    
    
    
    def save(self):
        """
        Saves the inode metadata record
        """
        # get inode metadata record as plain string
        irec_plain = self.pack()
    
        # encrypt it    
        self.icipher.setIV(self.iiv)
        irec_enc = self.icipher.encrypt(irec_plain)
    
        try:
            # and write it out
            f = file(self.ipath, "wb")
            f.write(irec_enc)
    
            # and write out some (encrypted) padding
            padding = self.genpaddinginode()
            #padding = self.icipher.encrypt(padding)
            f.write(padding)
        
            f.close()
    
            # and frig the timestamp
            t = randomInt(biggestTime)
            os.utime(self.ipath, (t, t))
        except:
            pass
    #@-node:save
    #@+node:load
    def load(self):
        """
        Loads a pre-existing layer root file from the store
        """
        # read in ciphertext
        f = file(self.ipath, "rb")
        irec_enc = f.read(self.sizeof)
        f.close()
        
        # decrypt it
        self.icipher.setIV(self.iiv)
        irec_plain = self.icipher.decrypt(irec_enc)
    
        # and unpack into this instance
        (inodenum,
         self.cfile,
         self.cpass,
         self.civ,
         self.type,
         self.nfiles,
         self.mode,
         self.dev,
         self.nlink,
         self.uid,
         self.gid,
         self.size,
         self.atime,
         self.mtime,
         self.ctime,
         ) = self.unpack(irec_plain)
    
        # wipe trailing zeros from the strings
        self.cfile = self.cfile.replace("\0", "")
        self.cpass = self.cpass.replace("\0", "")
        self.ccipher = SSLCrypto.blowfish(self.cpass, self.civ)
    
        # convenience stuff
        self.cpath = os.path.join(self.storedir, self.cfile)
        self.imageChunkNames = [self.cfile]
    
        # verify inode um
        if self.inode != inodenum:
            print "PANIC - mismatched inode numbers"
    #@-node:load
    #@+node:pack
    def pack(self):
        """
        Packs the inode data into a struct string
        """
        return struct.pack(self.fmt,
            self.inode,
            self.cfile,
            self.cpass,
            self.civ,
            self.type,
            self.nfiles,
            self.mode,
            self.dev,
            self.nlink,
            self.uid,
            self.gid,
            self.size,
            self.atime,
            self.mtime,
            self.ctime,
            )
    #@-node:pack
    #@+node:unpack
    def unpack(self, raw):
        """
        Unpacks a raw decrypted inode record
        """
        return struct.unpack(self.fmt, raw)
    #@-node:unpack
    #@+node:loadcontent
    def loadcontent(self):
        """
        Loads the content file into this object
        """
        # warm up the crypto
        cipher = self.ccipher
        cipher.setIV(self.civ)
    
        #print "LOADCONTENT: ENTERED"
    
        # how many chunks will this file take?
        numChunksNeeded = (self.size + contentChunkSize - 1) / contentChunkSize
    
        # load in and decrypt all the chunks
        filesize = pbconfig.filesize
        i = 0
        imageChunkNames = self.imageChunkNames
        image = array.array('c')
    
        #print "LOADCONTENT: chunks=%s, self.size=%s, filesize=%s" % (numChunksNeeded, self.size, filesize)
    
        while i < numChunksNeeded:
            # read encrypted chunk
            f = file(os.path.join(storedir, imageChunkNames[i]))
            enc = f.read(filesize)
            f.close()
            
            # decrypt
            plain = cipher.decrypt(enc)
    
            # get 'next filename' header and raw data
            nextname = plain[:filenamelength]
            rawdata = plain[filenamelength:]
    
            if i < numChunksNeeded-1:
                imageChunkNames.append(nextname)
            else:
                # at last block - truncate to ditch the padding
                lastchunksize = self.size % contentChunkSize
                if lastchunksize > 0:
                    rawdata = rawdata[:lastchunksize]
    
            #print "loadcontent: rawdata=%s" % repr(rawdata)
            image.fromstring(rawdata)
    
            i += 1
    
        self.image = image
    #@-node:loadcontent
    #@+node:savecontent
        #print "LOADCONTENT: done"
    
    
    def savecontent(self):
        """
        Saves the data image from this object to the content file(s)
        """
        # reset cipher
        cipher = self.ccipher
        cipher.setIV(self.civ)
        
        # encrypt the cached image
        #enc = cipher.encrypt("".join(self.image))
    
        try:
            if self.image.__class__ == list:
                print "YIKES - IMAGE HAS BECOME A LIST!!!"
                plain = array.array('c', self.image)
            else:
                plain = self.image
        except:
            plain = self.image
        
        #print "savecontent: image=%s"% repr(self.image.tostring())
    
        # how many chunks will this file take?
        numChunksNeeded = (self.size + contentChunkSize - 1) / contentChunkSize
        #print "numChunksNeeded = %s" % numChunksNeeded
    
        # make more chunkfile names if needed
        imageChunkNames = self.imageChunkNames
        i = len(imageChunkNames)
        while i < numChunksNeeded:
            imageChunkNames.append(randomFilename())
            i += 1
    
        # now encrypt and write all this shit out
        i = 0
        filesize = pbconfig.filesize
        while i < numChunksNeeded:
            # get, or bullshit, a 'next filename' header
            if i < numChunksNeeded-1:
                # non-final chunk - get name of next chunkfile
                nextChunk = self.imageChunkNames[i+1]
            else:
                # final chunk - just dream up anything
                nextChunk = "%040x" % SSLCrypto.genrandom(160, -1)
            
            # construct the block
            try:
                chunk = nextChunk + plain[i*contentChunkSize : (i+1)*contentChunkSize].tostring()
                #print "savecontent: chunk=%s" % repr(chunk)
            except:
                traceback.print_exc()
                print "nextChunk is a %s, %s" % (type(nextChunk), repr(nextChunk))
                raise
    
            # pad if needed
            chunklen = len(chunk)
            if chunklen < filesize:
                chunk += randomPadding(filesize - chunklen)
    
            # encrypt and write it out
            enc = cipher.encrypt(chunk)
            path = os.path.join(storedir, imageChunkNames[i])
            f = file(path, "wb")
            f.write(enc)
            f.close()
    
            t = randomInt(biggestTime)
            os.utime(path, (t, t))
    
            #print "wrote chunk length of %s" % len(enc)
    
            i += 1
    
        #print "release: SIZE = %s,%s,%s" % (self.size, len(self.image), len(enc))
        self.save()
    #@-node:savecontent
    #@+node:wipecontent
    def wipecontent(self):
        """
        Erases all the content files
        """
        # warm up the crypto
        cipher = self.ccipher
        cipher.setIV(self.civ)
    
        #print "WIPECONTENT: ENTERED"
    
        # load in and decrypt all the chunks
        imageChunkNames = self.imageChunkNames
    
        #print "LOADCONTENT: chunks=%s, self.size=%s, filesize=%s" % (numChunksNeeded, self.size, filesize)
    
        for chname in imageChunkNames:
            try:
                os.unlink(os.path.join(storedir, chname))
            except:
                pass
        self.imageChunkNames = []
        self.size = 0
        self.image = array.array('c')
    #@-node:wipecontent
    #@+node:savedir
        #print "WIPECONTENT: done"
    
    def savedir(self):
        """
        Saves the directory entries to the content file
        
        Format of each entry is:
            - <inode-num>:<filename><newline>
        """
        # generate dir entry lines
        image = self.image = array.array('c')
        for name, inodeobj in self.direntries.items():
            plaintext = "%d:%s\n" % (inodeobj.inode, name)
            image.fromstring(plaintext)
        self.size = len(self.image)
    
        self.savecontent()
        self.save()
    #@-node:savedir
    #@+node:loaddir
    def loaddir(self):
        """
        Loads a directory from content file, and gets refs to inode
        objects for all the entries
        
        File format is:
            - dir_entries
            - <newline><newline>
            - random padding
    
        Format of dir_entry is:
            - <inode-num>:<filename><newline>
        """
        # get the raw dir listing
        self.loadcontent()
        plaintext = self.image.tostring()
        
        # break it up
        #print "LOADDIR: raw='%s'" % repr(plaintext)
    
        plaintext = plaintext.split("\n\n", 1)[0] # toss any padding
        entries = plaintext.split("\n")
    
        #print repr(entries)
    
        if entries[-1] == '':
            entries = entries[:-1]
    
        # and load our local dict
        layer = self.layer
        direntries = self.direntries
        for entry in entries:
            #print "LOADDIR: %s" % entry
            instr, name = entry.split(":")
            inodenum = int(instr)
            inodeobj = layer.getInode(inodenum)
            direntries[name] = inodeobj
    
        # mark as loaded
        self.dirisloaded = 1
    #@-node:loaddir
    #@+node:x__getattr__
    def x__getattr__(self, attr):
        if attr in ['__nonzero__', '__len__', '__repr__', '__str__']:
            raise AttributeError
    
        if not self.dirisloaded:
            self.loaddir()
        return self.direntries[attr]
    #@-node:x__getattr__
    #@+node:handleCmd
    def handleCmd(self, parent, cmd, pathbits, args):
        """
        Either execute a kernel fs command in this layer, or
        pass the command down to a subdirectory or file.
        """
        #print "inode.handleCmd: %s:%s" % (cmdnames[cmd], repr(pathbits))
    
        #if cmd in [CMD_UNLINK, CMD_RMDIR, CMD_SYMLINK, CMD_RENAME,
        #           CMD_LINK, CMD_MKNOD, CMD_MKDIR]:
        #    # these commands are applied to current dir
        #    if pathbits and pathbits[0] != '':
    
        # are we second from end of path?
        #print "pathbits = %s" % repr(pathbits)
        if len(pathbits) == 1:
            # yes - some commands must apply at this level
            # this breaks the otherwise seamless recursive symmetry
            name = pathbits[0]
            if cmd == CMD_MKDIR:
                return self.mkdir(name, args[0])
            elif cmd == CMD_MKNOD:
                return self.mknod(name, args[0], args[1])
            elif cmd == CMD_UNLINK:
                return self.unlink(name)
            elif cmd == CMD_RMDIR:
                return self.rmdir(name)
            elif cmd == CMD_RENAME:
                return self.rename(name, args[0])
            elif cmd == CMD_LINK:
                return self.link(name, args[0])
            elif cmd == CMD_SYMLINK:
                return self.symlink(name, args[0])
            elif cmd == CMD_READLINK:
                return self.readlink(name)
            elif cmd == CMD_FIND_INODE:
                return self.findInode(name)
    
        # are we at the end of the dir path?
        if pathbits:
            # no - still one or more dirs to descend
            if self.type != 'd':
                raise PbOSError(ENOTDIR, "Not a directory")
            if not self.dirisloaded:
                self.loaddir()
            top, rest = pathbits[0], pathbits[1:]
            frec = self.direntries.get(top, None)
            if frec:
                # pass command to file or subdir in this dir
                #print "inode.handleCmd: found inode '%s'" % top
                return frec.handleCmd(self, cmd, rest, args)
            else:
                #if cmd not in [CMD_MKNOD, CMD_MKDIR]:
                #    print "trying to operate on nonexistent file/subdir '%s'" % repr(top)
                #    raise PbOSError(ENOENT, "No such file/dir '%s'" % top)
                #else:
                #    pass # handle in this dir
                #print "inode.handleCmd: no such file/dir '%s'" % top
                if self.fs.debug:
                    print "exception fetching dir '%s' - ***********" % top
                raise PbOSError(ENOENT, "No such file/dir '%s'" % top)
    
        # empty pathbits means operate on this file or dir
        if cmd == CMD_GETATTR:
            return self.getattr()
        elif cmd == CMD_GETDIR:
            return self.getdir()
        elif cmd == CMD_CHMOD:
            return self.chmod(args[0])
        elif cmd == CMD_CHOWN:
            return self.chown(args[0], args[1])
        elif cmd == CMD_TRUNCATE:
            return self.truncate(args[0])
        elif cmd == CMD_UTIME:
            return self.utime(args[0])
        elif cmd == CMD_OPEN:
            return self.open(args[0])
        elif cmd == CMD_READ:
            return self.read(args[0], args[1])
        elif cmd == CMD_WRITE:
            return self.write(args[0], args[1])
        elif cmd == CMD_RELEASE:
            return self.release(args[0])
        elif cmd == CMD_FSYNC:
            return self.fsync(args[0])
        elif cmd == CMD_FIND_INODE:
            return self.findInode(None, 0)
    #elif cmd == CMD_MKNOD:
        #    return self.mknod(pathbits[0], args[0], args[1])
        #elif cmd == CMD_MKDIR:
        #    return self.mkdir(pathbits[0], args[0])
        else:
            raise PbOSError(EPERM, "Bad command ID %s" % cmd)
    #@-node:handleCmd
    #@+node:getattr
    def getattr(self):
        """
        Return the following in a tuple (or -1 if failed)
            #st_mode (protection bits)
            #st_ino (inode number)
            #st_dev (device)
            #st_nlink (number of hard links)
            #st_uid (user ID of owner)
            #st_gid (group ID of owner)
            #st_size (size of file, in bytes)
            #st_atime (time of most recent access)
            #st_mtime (time of most recent content modification)
            #st_ctime (time of most recent content modification or metadata change).
    
        """
        #print "inode.getattr: "
    
        if self.type == 'd':
            size = 1024
        else:
            size = self.size
        attr = (self.mode,
                self.inode,
                self.dev,
                self.nlink,
                self.uid,
                self.gid,
                size,
                self.atime,
                self.mtime,
                self.ctime,
                )
        #print "inode.getattr: got (0%o %s %s %s %s %s %s %s %s %s)" % attr
        return attr
    #@-node:getattr
    #@+node:getdir
    def getdir(self):
        #print "inode.getdir: "
    
        if not self.dirisloaded:
            self.loaddir()
    
        names = self.direntries.keys()
        names.sort()
    	lst = map(lambda x: (x,0), names)
        if self.fs.debug:
            print lst
        return lst
    #@-node:getdir
    #@+node:unlink
    def unlink(self, name):
        """
        Unlink a dir entry
        """
        #print "inode.unlink: %s" % name
    
        if not self.dirisloaded:
            self.loaddir()
    
        inode = self.direntries.get(name, None)
        if not inode:
            raise PbOSError(ENOENT, "No such file/directory '%s'" % name)
    
        if inode.type == 'd':
            print "IS A DIRECTORY!"
            raise PbOSError(EISDIR, "this is a directory")
    
        # ok to remove
        inode.nlink -= 1
        if inode.nlink <= 0:
            # delete content file(s)
            inode.wipecontent()
    
            # delete inode file
            try:
                os.unlink(inode.ipath)
            except:
                traceback.print_exc()
                pass
        del self.direntries[name]
        self.nfiles -= 1
        self.savedir()
        return 0
    #@-node:unlink
    #@+node:rmdir
    def rmdir(self, name):
        """
        We must kill ourselves from the filesystem, if empty
        """
        #print "inode.rmdir: %s" % name
    
        if self.type != 'd':
            raise PbOSError(ENOTDIR, "Not a directory")
    
        if not self.dirisloaded:
            self.loaddir()
    
        inode = self.direntries.get(name, None)
        if not inode:
            raise PbOSError(ENOENT, "No such directory '%s'" % name)
    
        if inode.nfiles > 0:
            raise PbOSError(ENOTEMPTY, "Directory not empty")
    
        # ok to remove
        inode.nlink -= 1
        if inode.nlink <= 0:
            # delete content file
            if os.path.isfile(inode.cpath):
                try:
                    os.unlink(inode.cpath)
                except:
                    traceback.print_exc()
                    pass
            # delete inode file
            try:
                #traceback.print_exc()
                os.unlink(inode.ipath)
            except:
                pass
        del self.direntries[name]
        self.nfiles -= 1
        self.savedir()
        return 0
    #@-node:rmdir
    #@+node:link
    def link(self, name, target):
    
        print "inode.link: %s -> %s" % (name, target)
    
        # raise PbOSError(EPERM, "Device does not support hard links")
    
        try:
            if not self.dirisloaded:
                self.loaddir()
            
            if name in self.direntries.keys():
                raise PbOSError(EEXIST, "file %s already exists" % repr(filename))
        
            # try to find the target inode within current layer
            inode, isparent = self.layer.root.handleCmd(self.layer,
                                                        CMD_FIND_INODE,
                                                        target.split("/")[1:],
                                                        [])
            
            if isparent:
                raise PbOSError(ENOENT, "Link target '%s' does not exist" % target)
        
            # seems we've found the target in current layer - link it in
            inode.nlink += 1
            self.direntries[name] = inode
            self.nfiles += 1
            self.savedir()
        except:
            traceback.print_exc()
            print "inode.link: SCREWED UP"
            raise
    
        #print "inode.link: seems ok"
        return 0
    #@-node:link
    #@+node:symlink
    def symlink(self, name, target):
    
        #print "inode.symlink: name='%s' target='%s'" % (name, target)
    
        if not self.dirisloaded:
            self.loaddir()
        
        if name in self.direntries.keys():
            raise PbOSError(EEXIST, "file %s already exists" % repr(filename))
    
        # create the symlink file
        inode = self.layer.getInode(type='l', mode=0666)
        inode.nlinks = 1
    
        # add symlink file to this dir
        self.direntries[name] = inode
        self.nfiles += 1
        self.savedir()
    
        # write the target file
        inode.mode = inode.mode | S_IFLNK
        inode.image = array.array('c', target)
        inode.size = len(target)
        inode.savecontent()
        return 0
    #@-node:symlink
    #@+node:readlink
    def readlink(self, name):
    
        #print "inode.readlink: %s" % name
    
        if not self.dirisloaded:
            self.loaddir()
    
        inode = self.direntries.get(name, None)
        if not inode:
            raise PbOSError(ENOENT, "No such file '%s'" % name)
    
        if not (inode.mode & S_IFLNK):
            raise PbOSError(ENOLINK, "'%s' is not a link" % name)
        
        # seems ok - read/decrypt
        inode.loadcontent()
        return inode.image.tostring()
    #@-node:readlink
    #@+node:rename
    def rename(self, oldname, newpath):
    
        #print "inode.rename: %s %s" % (oldname, newpath)
    
        if not self.dirisloaded:
            self.loaddir()
    
        oldinode = self.direntries.get(oldname, None)
        if not oldinode:
            raise PbOSError(ENOENT, "No such file/directory '%s'" % name)
    
        # get inode for new name or its parent
        newinode, isparent = self.fs.findInode(newpath)
        if not newinode:
            raise PbOSError(ENOENT, "No such file/dir '%s'" % newname)
        newname = os.path.split(newpath)[1]
        if newname == '':
            newname = oldname
    
        if not newinode.dirisloaded:
            newinode.loaddir()
    
        if isparent:
            pass
        else:
            if newinode.type != 'd':
                raise PbOSError(ENOTDIR, "not a dir")
    
        # un-hitch the old inode entry
        try:
            #print "inode.rename: deleting old inode '%s'" % oldname
            del self.direntries[oldname]
        except:
            traceback.print_exc()
            print "rename exc 1"
        self.nfiles -= 1
        self.savedir()
        self.save()
    
        # and move the inode into new parent, under new name
        #print "newname = '%s'" % newname
        newinode.direntries[newname] = oldinode
        newinode.nfiles += 1
        newinode.savedir()
    
        return 0
    #@-node:rename
    #@+node:chmod
    def chmod(self, mode):
    
        #print "inode.chmod: 0%o" % mode
        self.mode = mode
        self.save()
        return 0
    #@-node:chmod
    #@+node:chown
    def chown(self, user, group):
    
        #print "inode.chown: %s %s" % (user, group)
    
        self.uid = user
        self.gid = group
        self.save()
        return 0
    #@-node:chown
    #@+node:truncate
    def truncate(self, size):
    
        #print "inode.truncate: %s" % size
    
        self.size = size
        try:
            self.image = self.image[:size]
        except:
            traceback.print_exc()
            print "truncate fuckup"
        #print "inode.truncate: done"
        return 0
    #@-node:truncate
    #@+node:mknod
    def mknod(self, filename, mode, dev):
        """
        Create a file within this directory
        """
        #print "inode.mknod: %s 0%o %s" % (filename, mode, dev)
    
        try:
            if not self.dirisloaded:
                self.loaddir()
            
            if filename in self.direntries.keys():
                raise PbOSError(EEXIST, "file %s already exists" % repr(filename))
        
            inode = self.layer.getInode(type='f', mode=mode, dev=dev)
        
            inode.nlinks = 1
            self.direntries[filename] = inode
            self.nfiles += 1
            self.savedir()
            #print "inode.mknod: done"
        except:
            if self.fs.debug:
                traceback.print_exc()
                print "mknod: weird exception"
            raise
    
        return 0
    #@-node:mknod
    #@+node:mkdir
    def mkdir(self, dirname, mode):
        """
        Create a subdirectory of this directory
        """
        #print "inode.mkdir: %s 0%o" % (dirname, mode)
    
        inode = self.layer.getInode(type='d', mode=mode)
    
        inode.nlinks = 1
        self.direntries[dirname] = inode
        self.nfiles += 1
        self.savedir()
        return 0
    #@-node:mkdir
    #@+node:utime
    def utime(self, times):
    
        #print "inode.utime: %s" % (repr(times),)
    
        self.atime, self.mtime = times
        self.save()
        return 0
    #@-node:utime
    #@+node:open
    def open(self, flags):
    
        #print "inode.open: %s" % (flags,)
        
        # this is pretty inefficient, but better than before
        # on first open, the whole file gets read in.
        # on any close with write flags, the file gets written out
        
        if self.numopen == 0:
    
            #print "open: ACQUIRING LOCK"
            self.lock.acquire()
            #print "open: GOT LOCK"
    
            try:
                self.loadcontent()
                #print "open: SIZE = %d->%d" % (len(enc), len(self.image))
                self.numopen += 1
            except:
                traceback.print_exc()
        
            #print "open: RELEASING LOCK"
            self.lock.release()
    
        return 0
    #@-node:open
    #@+node:release
    def release(self, flags):
        #print "inode.release: %s" % (flags,)
    
        # if flags indicate any kind of writing, then we gotta encrypt and write out
        # the whole thing
        
        if flags & (os.O_CREAT | os.O_APPEND | os.O_WRONLY | os.O_RDWR | os.O_TRUNC):
    
            #print "release: ACQUIRING LOCK"
            self.lock.acquire()
            #print "release: GOT LOCK"
    
            try:
                self.savecontent()
                pass
            except:
                traceback.print_exc()
                print "RELEASE FAIL"
                print "image = '%s'" % repr(self.image)
        
            #print "release: RELEASING LOCK"
            self.lock.release()
    
        self.numopen -= 1
        if self.numopen <= 0:
            self.image = array.array('c')
    
        #print "release: DONE"
        return 0
    #@-node:release
    #@+node:read
    def read(self, nbytes, offset):
    
        #print "inode.read: %s %s" % (nbytes, offset)
        #print "image class = %s" % self.image.__class__
    
        #print "read: ACQUIRING LOCK"
        self.lock.acquire()
        #print "read: GOT LOCK"
    
        try:
            #chunk = "".join(self.image[offset:offset+nbytes])
            slice = self.image[offset:offset+nbytes]
            try:
                if slice.__class__ == list:
                    print "YIKES - AN ARRAY HAS BECOME A LIST!!!"
                    slice = array.array('c', slice)
            except:
                pass
            chunk = slice.tostring()
        except:
            traceback.print_exc()
            print "READ FAIL"
            chunk = ''
            print "image type = %s" % type(self.image)
    
        #print "read: RELEASING LOCK"
        self.lock.release()
    
        #print "READ DONE, SIZE=%s, chunk='%s'" % (len(chunk), chunk)
        return chunk
    #@-node:read
    #@+node:write
    def write(self, buf, offset):
    
        size = len(buf)
    
        #print "inode.write: %s %s" % (offset, size)
        #print "image class = %s" % self.image.__class__
    
        #print "write: ACQUIRING LOCK"
        self.lock.acquire()
        #print "write: GOT LOCK"
        
        # fudge a slice assignment
        try:
            #self.image = self.image[0:offset] + buf + self.image[offset+size:]
            #self.image[offset:offset+size] = buf
            self.image[offset:offset+size] = array.array('c', buf)
            #print "image class = %s" % self.image.__class__
        except:
            traceback.print_exc()
            print "WRITE FAIL"
    
        # adjust size if needed
        if self.size < size + offset:
            self.size = size + offset
    
        #print "write: RELEASING LOCK"
        self.lock.release()
    #@-node:write
    #@+node:fsync
    def fsync(self, isfsyncfile):
    
        #print "inode.fsync: isfsyncfile=%s" % isfsyncfile
    
        return 0
    #@-node:fsync
    #@+node:statfs
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
        #print "inode.statfs: returning fictitious values"
        blocks_size = 65536
        blocks = 100000
        blocks_free = 25000
        files = 100000
        files_free = 60000
        namelen = 80
        return (blocks_size, blocks, blocks_free, files, files_free, namelen)
    #@-node:statfs
    #@+node:findInode
    def findInode(self, name, isFromParent=1):
        """
        Quirky internal method for retrieving a file/dir object
        by its pathname
        
        Returns:
            - tuple (fileobj, isparent):
                - fileobj - file object corresponding to path if path exists, or obj of parent
                - isparent - 1 if returning the parent directory, 0 if not
        """
        if isFromParent:
     
            #print "inode.findInode: seeking inode amongst dir entries"
     
            if not self.dirisloaded:
                self.loaddir()
            #print "inode.findInode: direntries = '%s'" % self.direntries
            obj = self.direntries.get(name, None)
            if obj:
                return obj, 0
            else:
                return self, 1
        else:
            #print "we are the inode"
            return self, 0
    #@-node:findInode
    #@+node:createPool
    def createPool(self, size):
        
        """
        Only used if this inode is of type 'pool'
        
        Creates a pool of random datastore files, which get used whenever a new
        file is created.
        """
        # how big should this be in bytes?
        if poolsize == '':
            poolsize = 65536
        else:
            suffix = poolsize[:-1].lower()
            if suffix == 'k':
                poolsize = int(poolsize[:-1]) * 1024
            elif suffix == 'm':
                poolsize = int(poolsize[:-1]) * 1024 * 1024
            elif suffix == 'g':
                poolsize = int(poolsize[:-1]) * 1024 * 1024 * 1024
    #@-node:createPool
    #@+node:genpaddinginode
    def genpaddinginode(self):
        """
        Generates a random amount of random padding data
        for the inode file
        """
        return randomPadding(pbconfig.filesize - self.sizeof)
    #@-node:genpaddinginode
    #@+node:genpaddingcontent
    def genpaddingcontent(self):
        """
        Generates a random amount of random padding data
        for the content file
        """
        print "SHIT!!!"
        return randomPadding(pbconfig.minpadding, pbconfig.maxpadding)
    #@-node:genpaddingcontent
    #@-others

Inode.sizeof = struct.calcsize(Inode.fmt)
#@nonl
#@-node:class Inode
#@+node:PbOSError
def PbOSError(errno, msg):
    """
    Creates an OSError exception object and fills in errno
    
    Args:
        - errno - any of the constants in module 'stat'
        - msg - text of the error
    """
    e = OSError(msg)
    e.errno = errno
    return e

#@-node:PbOSError
#@+node:randomFilename
def randomFilename():
    """
    Generates and returns a random filename (string, 40 bytes),
    guaranteed not to be an existing filename in the datastore
    """

    #global fuckup
    #if fuckup >= 20:
    #    try:
    #        raise Exception
    #    except:
    #        traceback.print_exc()
    #        raise
    #else:
    #    fuckup += 1

    storedirfiles = os.listdir(storedir)

    #safety = 20
    #i = 0
    while 1:
        #if i >= safety:
        #    print "randomFilename: aarghhh!"
        #    raise Exception("randomFilename: crisis!!")
        #i += 1
        name = "%040x" % SSLCrypto.genrandom(160, -1)
        if name not in storedirfiles:
            # create a file full of random shit
            try:
                #print "creating random content"
                shit = randomPadding(pbconfig.filesize)
                path = os.path.join(storedir, name)
                #print "writing random content to new file %s" % path
                file(path, "wb").write(shit)

                #print "random content created"
            except:
                print "failed to create random content"
            return name

    #raise Exception("WTF is going on?")

#@-node:randomFilename
#@+node:randomNumber
def randomNumber(nbits):
    """
    Generates and returns a random integer,
    """
    while 1:
        n = SSLCrypto.genrandom(nbits, -1)
        if n != 0:
            return int(n)
#@-node:randomNumber
#@+node:randomInt
def randomInt(arg1, arg2=None):
    """
    Generates and returns a random integer,
    """
    if arg2 == None:
        min = 0
        max = arg1
    else:
        min = arg1
        max = arg2
    n = SSLCrypto.genrandom(128, -1)
    return min + int(n % (max-min))

#@-node:randomInt
#@+node:randomPassphrase
def randomPassphrase():
    """
    Generates and returns a random passphrase (string, 32 bytes)
    """
    return "%064x" % SSLCrypto.genrandom(256, -1)
#@-node:randomPassphrase
#@+node:randomIv
def randomIv():
    """
    Generates and returns a random IV (string, 8 bytes)
    """
    return SSLCrypto.long_to_bytes(SSLCrypto.genrandom(72))[:8]

#@-node:randomIv
#@+node:randomPadding
def randomPadding(minbytes, maxbytes=None):
    """
    Generates a random amount of random data as a string,
    length between minbytes and maxbytes-1 (inclusive)
    
    Omit maxbytes to get a random chunk of exactly 'minbytes' length
    """
    if maxbytes != None:
        size = randomInt(minbytes, maxbytes)
    else:
        size = minbytes
    return urandom.read(size)
#@-node:randomPadding
#@+node:filemode
def filemode(**kw):
    pass
#@-node:filemode
#@+node:hash
def hash(txt):
    """
    creates a hash of a string, as legal filename characters
    """
    return sha1(txt).hexdigest()
#@-node:hash
#@+node:isspecial
def isspecial(pathbits):
    
    res = pathbits[0].startswith(cmdFile) or pathbits[0].startswith(respFile)
    #if res:
    #    b = ""
    #else:
    #    b = "NOT "
    #print "%s is %sspecial (%s)" % (repr(pathbits), b, cmdFile)
    return res

#@-node:isspecial
#@+node:usage
def usage(ret):
    print "Usage: %s /path/of/storedir /path/of/mountpoint [-o opt1=val1[,...]]" % progname
    sys.exit(ret)
#@-node:usage
#@+node:main
def main():
    #print "phonebookfs.py: argv=%s" % repr(sys.argv)
    server = PhoneBookFs()
    server.flags = 0
    server.multithreaded = 1;
    #print "PhoneBookFs: mounted %s as %s" % (repr(server.storedir), repr(server.mountpoint))
    server.main()

#@-node:main
#@+node:mainline

if __name__ == '__main__':

    main()
#@-node:mainline
#@-others
#@-node:@file phonebookfs.py
#@-leo

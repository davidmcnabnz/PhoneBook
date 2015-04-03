#!/usr/bin/env python
#@+leo-ver=4
#@+node:@file mount.py
#@@first

"""
This utility allows the PhoneBook filesystem to be mounted with the regular *nix
'mount' command, or even be listed in /etc/fstab

To enable this, you need to:
 1. set execute-permission on this script
 2. symlink this script into /sbin/mount.phonebook

Usage:

 mount -t pbfs none /path/of/mount/point -o storedir=/path/to/empty/dir,[...]

"""

import sys, os, time

progname = sys.argv[0]

def usage(ret):
    print "Usage: %s /path/of/storedir /path/of/mountpoint [-o opt1=val1[,...]]" % progname
    sys.exit(ret)

def main():

    # initial sanity check
    argv = sys.argv
    argc = len(argv)
    
    if 1 in [o in ['-h', '-?', '--h', '--help', 'help'] for o in argv]:
        usage(0)

    if argc < 3 or sys.argv[3] != "-o":
        usage(1)

    store = sys.argv[1]
    mountpoint = sys.argv[2]

    # grab options, if any
    optdict = {}
    optlist = []
    if argc > 4:
        odata = sys.argv[4]
        opts = odata.split(",")
        #print opts
        for o in opts:
            try:
                k, v = o.split("=", 1)
                optdict[k] = v
            except:
                optlist.append(o)
    else:
        odata = ""

    # add storedir to options
    if store not in ['/proc/fs/fuse/dev', 'none']:
        optdict['storedir'] = store
    odata = ",".join(optlist + [k+"="+v for k,v in optdict.items()])

    # determine abs path of our fs prog
    import mount
    pypath = os.path.join(os.path.split(os.path.abspath(mount.__file__))[0], "phonebookfs.py")

    # if we're running as root, offer shared access
    uid = os.getuid()
    if uid == 0:
        shareopt = "-x"
    else:
        shareopt = ""

    # all seems ok - run our fuse fs as a child
    if os.fork() == 0:
        #print store
        cmd = "fusermount -c %s -d %s %s %s %s %s" % (shareopt, store, mountpoint, pypath, mountpoint, odata)
        #print cmd
        os.system(cmd)
    else:
        #print "parent exiting..."
        pass

if __name__ == '__main__':
    main()

#@-node:@file mount.py
#@-leo

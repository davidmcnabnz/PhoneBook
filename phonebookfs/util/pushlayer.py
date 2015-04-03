#!/usr/bin/env python
#@+leo-ver=4
#@+node:@file util/pushlayer
#@@first

import sys, os

import pbdummy
sys.path.append(os.path.split(os.path.split(os.path.abspath(pbdummy.__file__))[0])[0])
import pbcmds

argv = sys.argv
argc = len(argv)
progname = argv[0]

def usage(ret=0):
    print "usage: %s mountpoint layername layerpass" % progname
    sys.exit(1)

def main():
    if argc != 4:
        usage(1)

    mountpoint = argv[1]    
    layername, layerpass = argv[2:4]
    
    res = pbcmds.sendPbCommand(mountpoint,
                               command='addlayer',
                               name=layername, passphrase=layerpass)
    #print "got: %s" % res
    if res['status'] != 'success':
        print "%s: failed: %s" % (progname, res['detail'])
    else:
        print "%s: success: %s" % (progname, res['detail'])
    
if __name__ == '__main__':
    main()

#@-node:@file util/pushlayer
#@-leo

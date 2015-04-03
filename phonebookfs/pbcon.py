#!/usr/bin/env python
#@+leo-ver=4
#@+node:@file pbcon.py
#@@first

"""
pbcon.py - provides a python console interface to the running filesystem
"""
#@+others
#@+node:imports
import sys, os
import readline

import pbcmds
#@-node:imports
#@+node:globals
argv = sys.argv
argc = len(argv)

#@-node:globals
#@+node:usage
def usage(ret=0):
    print "Usage: %s mountpoint" % argv[0]
    sys.exit(ret)
#@-node:usage
#@+node:main
def main():

    argv = sys.argv
    argc = len(argv)

    if argc == 1:
        print "Missing mountpoint"
        usage(1)
    mountpoint = argv[1]

    prompt = "pb>>> "

    # loop around, executing commands and reporting responses
    while 1:
        try:
            cmd = raw_input(prompt)
        except:
            print
            cmd = "q"

        if cmd in ['q', "quit"]:
            sys.exit(0)

        resp = pbcmds.sendPbCommand(mountpoint, command="pycmd", pycmd=cmd)
        if resp == {}:
            print "<<<" \
                  +"COMMAND FAILED>>>"
            print "resp = '%s'" % repr(resp)
        elif resp['status'] != 'success':
            print "<<<" \
                  +"COMMAND FAILED>>>"
            print resp['detail']
        else:
            #print resp['output']
            #print repr(resp['detail'])
            sys.stdout.write(resp['output'])
            sys.stdout.flush()
            if int(resp['cont']):
                prompt = "pb... "
            else:
                prompt = "pb>>> "


#@-node:main
#@+node:mainline
if __name__ == '__main__':
    main()

#@-node:mainline
#@-others
#@-node:@file pbcon.py
#@-leo

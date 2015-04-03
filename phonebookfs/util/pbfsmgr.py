#@+leo-ver=4
#@+node:@file util/pbfsmgr.py
import sys, os, getopt
import traceback

import pbdummy

def main():

    try:
        opts, args = getopt.getopt(args,
                                   "h?vqifl:n:p:P:S:H:D:V:L:T:",
                                   ['help', 'version',
                                    #'mountpoint', 
                                    #'node-address=', 'node-port=',
                                    ])
    except:
        import traceback
        traceback.print_exc(file=sys.stdout)
        usage("You entered an invalid option", 1)
#@-node:@file util/pbfsmgr.py
#@-leo

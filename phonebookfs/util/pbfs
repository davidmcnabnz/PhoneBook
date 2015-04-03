#!/usr/bin/env python
#@+leo-ver=4
#@+node:@file util/pbfs
#@@first
#@verbatim
#@first #!/usr/bin/env python2.2

import sys, os, getopt, getpass
import traceback

argv = sys.argv
argc = len(argv)
progname = argv[0]

import pbdummy
sys.path.append(os.path.split(os.path.split(os.path.abspath(pbdummy.__file__))[0])[0])
import pbcmds

def usage(msg, ret):
    print msg
    print "Usage: %s mountpoint command [args...]" % progname
    print "   or: %s -h|--help|help [command]" % progname
    sys.exit(ret)

def help(cmd=None):

    if cmd == 'help':
        print "For general help, type '%s -h'" % progname
        print "For detailed command help, type '%s -h command'" % progname

    elif cmd == 'openmap':
        print "Syntax: %s mountpoint openmap mapname [mappass]" % progname
        print "Closes current layermap, and opens/activates the map as specified"
        print "by mapname and mappass. If the map doesn't exist, it will be"
        print "created. Note that it's ok to have two or more maps with the"
        print "same name but different passphrases, which might suit your"
        print "security arrangements nicely."
        print
        print "If you do not give the passphrase, you will be prompted for it"
        print "(which is probably a wise move, to stop it ending up in shell"
        print "history files)."
    
    elif cmd == 'listmap':
        print "Syntax: %s mountpoint listmap" % progname
        print "Displays the currently active pbfs layermap (if any), "
        print "as well as any layers contained therein"

    elif cmd == 'destroymap':
        print "Syntax: %s mountpoint destroymap mapname [mappass]" % progname
        print "Destroys a layermap"
        print
        print "If you do not give the passphrase, you will be prompted for it"
        print "(which is probably a wise move, to stop it ending up in shell"
        print "history files)."
      
    elif cmd == 'addlayer':
        print "Syntax: %s mountpoint addlayer layername [layerpass]" % progname
        print "Activates a filesystem layer, and appends it to the bottom of the "
        print "current layermap's stack (giving it last precedence when"
        print "searching for files)"
        print
        print "If you do not give the passphrase, you will be prompted for it"
        print "(which is probably a wise move, to stop it ending up in shell"
        print "history files)."
    
    elif cmd == 'pushlayer':
        print "Syntax: %s mountpoint pushlayer layername [layerpass]" % progname
        print "Activates a filesystem layer, and puts it at the top of the "
        print "current layermap's stack (giving it first precedence when"
        print "searching for files)"
        print
        print "If you do not give the passphrase, you will be prompted for it"
        print "(which is probably a wise move, to stop it ending up in shell"
        print "history files)."
    
    elif cmd == 'droplayer':
        print "Syntax: %s mountpoint droplayer layername" % progname
        print "Removes the named layer from the current layermap stack"
        print "Does not delete the layer or its files"
    
    elif cmd == 'poplayer':
        print "Syntax: %s mountpoint poplayer" % progname
        print "Deactivates the layer at the top of the current layermap stack."
        print "Does not delete the layer or its files."

    elif cmd == 'makechaff':
        print "Syntax: %s mountpoint makechaff size" % progname
        print "Adds 'size' bytes worth of chaff files to the datastore"
        print "The 'size' may be suffixed by 'k', 'm' or 'g' to indicate"
        print "kilobytes, megabytes or gigabytes, respectively"

    else:
        print "Usage: %s mountpoint command [args...]" % progname
        print "   or: %s -h|--help|help [command]" % progname
        print "Available commands:"
        print "  help                             Show this help"
        print "  help [command]                   Show help on a particular command"
        print "  listmap                          Show details of current layermap"
        print "  openmap mapname [mappass]        Opens a different layermap"
        print "  destroymap mapname [mappass]     Destroys a layermap"
        print "  addlayer layername [layerpass]   Opens layer 'layername', appends to bottom of stack"
        print "  pushlayer layername [layerpass]  Opens layer 'layername', pushes to top of stack"
        print "  droplayer layername              Removes named layer 'layername' from stack"
        print "  poplayer                         Removes the topmost layer from stack"
        print "  makechaff size                   Pollutes datastore with 'size' bytes of chaff"

    sys.exit(0)

def mountpoints():
    lines = file("/proc/mounts").readlines()
    mounts = {}
    for line in lines:
        dev, mtpt, fstype, flags, freq, passno = line.strip().split(" ")
        mounts[mtpt] = {'device':dev, 'type':fstype, 'freq':freq, 'passno':passno}
    return mounts

def main():

    #try:
    #    opts, args = getopt.getopt(args,
    #                               "h?vqifl:n:p:P:S:H:D:V:L:T:",
    #                               ['help', 'version',
    #                                #'mountpoint', 
    #                                #'node-address=', 'node-port=',
    #                                ])
    #except:
    #    import traceback
    #    traceback.print_exc(file=sys.stdout)
    #    usage("You entered an invalid option", 1)

    if argc > 1 and (argv[1] in ['-h', 'help', '--help']):
        if argc > 2:
            help(argv[2])
        else:
            help()

    if argc < 2:
        usage("Missing mountpoint", 1)
    mountpoint = argv[1]

    if mountpoint in ['-h', '-help', '--help', 'help']:
        if argc == 2:
            help()
        else:
            help(argv[3])

    if 1 in [o in ['-h', '-?', '--h', '--help', 'help'] for o in argv]:
        help()

    # validate mountpoint
    mounts = mountpoints()
    if not ((mountpoint in mounts.keys()) and os.path.isdir(os.path.join(mountpoint, "__layers"))):
        usage("Invalid mountpoint '%s' - not a pbfs filesystem" % mountpoint, 1)

    if argc < 3:
        usage("Missing command word", 1)
    cmd = argv[2]

    if cmd == 'help':
        if argc >= 4:
            help(argv[3])
        else:
            help()

    # ------------------------------------
    # addlayer
    elif cmd == 'addlayer':

        if argc not in [4, 5]:
            help()

        layername = argv[3]
        if argc == 4:
            layerpass = getpass.getpass("PB Layer Passphrase: ")
        else:
            layerpass = argv[4]

        res = pbcmds.sendPbCommand(mountpoint,
                                   command='addlayer',
                                   name=layername,
                                   passphrase=layerpass,
                                   )
        if res['status'] != 'success':
            print "%s: failed: %s" % (progname, res['detail'])
        else:
            print "%s: success: %s" % (progname, res['detail'])

    # ------------------------------------
    # pushlayer
    elif cmd == 'pushlayer':
        if argc not in [4, 5]:
            help()

        layername = argv[3]
        if argc == 4:
            layerpass = getpass.getpass("PB Layer Passphrase: ")
        else:
            layerpass = argv[4]

        res = pbcmds.sendPbCommand(mountpoint,
                                   command='pushlayer',
                                   name=layername,
                                   passphrase=layerpass,
                                   )
        if res['status'] != 'success':
            print "%s: failed: %s" % (progname, res['detail'])
        else:
            print "%s: success: %s" % (progname, res['detail'])

    # ------------------------------------
    # droplayer
    elif cmd == 'droplayer':
        if argc != 4:
            help()
        layername = argv[3]
        res = pbcmds.sendPbCommand(mountpoint,
                                   command='droplayer',
                                   name=layername,
                                   )
        if res['status'] != 'success':
            print "%s: failed: %s" % (progname, res['detail'])
        else:
            print "%s: success: %s" % (progname, res['detail'])

    # ------------------------------------
    # poplayer
    elif cmd == 'poplayer':
        res = pbcmds.sendPbCommand(mountpoint,
                                   command='poplayer',
                                   )
        if res['status'] != 'success':
            print "%s: %s: failed: %s" % (progname, mountpoint, res['detail'])
        else:
            print "%s: %s: success: %s" % (progname, mountpoint, res['detail'])

    # ------------------------------------
    # openmap
    elif cmd == 'openmap':
        if argc not in [4, 5]:
            help()

        mapname = argv[3]
        if argc == 4:
            mappass = getpass.getpass("PB Map Passphrase: ")
        else:
            mappass = argv[4]

        res = pbcmds.sendPbCommand(mountpoint,
                                   command='openmap',
                                   name=mapname,
                                   passphrase=mappass,
                                   )
        if res['status'] != 'success':
            print "%s: failed: %s" % (progname, res['detail'])
        else:
            print "%s: success: %s" % (progname, res['detail'])

    # ------------------------------------
    # destroymap
    elif cmd == 'destroymap':
        if argc not in [4, 5]:
            help()
        mapname = argv[3]
        if argc == 4:
            mappass = getpass.getpass("PB Map Passphrase: ")
        else:
            mappass = argv[4]
        #mapname, mappass = argv[3], argv[4]
        res = pbcmds.sendPbCommand(mountpoint,
                                   command='destroymap',
                                   name=mapname,
                                   passphrase=mappass,
                                   )
        if res['status'] != 'success':
            print "%s: failed: %s" % (progname, res['detail'])
        else:
            print "%s: success: %s" % (progname, res['detail'])

    # ------------------------------------
    # listmap
    elif cmd == 'listmap':

        res = pbcmds.sendPbCommand(mountpoint,
                                   command='listmap',
                                   )
        #print "got: %s" % res
        mapname = res['mapname']
        if mapname == '':
            showmapname = "** USING TEMPORARY SCRATCH MAP **"
        else:
            showmapname = mapname
        print "PhoneBookFS Layer Map Report:"
        print "  Mountpoint: %s" % mountpoint
        print "  Map Name:   %s" % showmapname
        if res['layers'] == '':
            layers = "** NO LAYERS CURRENTLY IN MAP **"
        else:
            layers = ":".join(res['layers'].split("/"))
        print "  Layers:     %s" % layers


    # ------------------------------------
    # makechaff
    elif cmd == 'makechaff':

        if argc != 4:
            help()
        size = argv[3]

        sys.stdout.write("makechaff: this might take a while, please be patient...")
        sys.stdout.flush()
        res = pbcmds.sendPbCommand(mountpoint,
                                   command='makechaff',
                                   size=size,
                                   )
        print

        if res['status'] != 'success':
            print "%s: failed: %s" % (progname, res['detail'])
        else:
            print "%s: success: %s" % (progname, res['detail'])

    else:
        help()

if __name__ == '__main__':
    main()



#@-node:@file util/pbfs
#@-leo

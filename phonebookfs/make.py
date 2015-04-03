#!/usr/bin/env python
#@+leo-ver=4
#@+node:@file make.py
#@@first
#@verbatim
#@first #!/usr/bin/env python2.2

# If your kernel headers are in a weird place, set the kernelHeaders
# var below to the right value
#kernelHeaders = '--with-kernel=/usr/src/kernel-headers-2.4.18'
kernelHeaders = ''

"""
install.py

Build/Install file for PhoneBook filesystem
Constructs the dependencies, and sets everything up as needed for
the filesystem code to run out of this directory
"""

import sys, os, getpass


progname = sys.argv[0]
username = getpass.getuser()
sh = os.system

pythoncmd = "python"
#pythoncmd = "python2.2"

fusedir = os.path.join("pbmodules", "src", "fuse")
fusepydir = os.path.join(fusedir, "python")
fusepyfiles = ["_fusemodule.so", "fuse.py"]
cryptodir = os.path.join("pbmodules", "src", "crypto")
cryptofiles = ["SSLCrypto.so"]

makedonefile = ".make_done"

def doInDir(indir, cmd):
    "runs shell command in dir"
    ret = os.system("cd %s && %s" % (indir, cmd))
    if ret:
        print "COMMAND '%s' FAILED" % cmd
        sys.exit(ret)

def makeBuild():
    print "Building FUSE..."
    print "** Running autoshit"
    #print "** Automake disabled for now"
    doInDir(fusedir, "./makeconf.sh")
    print "** invoking FUSE configure"
    doInDir(fusedir, "./configure %s" % kernelHeaders)
    print "** invoking FUSE make"
    doInDir(fusedir, "make")
    print "** making FUSE python module"
    doInDir(fusepydir, "rm -f fuse.h && ln -s ../include/fuse.h fuse.h")
    doInDir(fusepydir, pythoncmd+" setup.py build_ext --inplace")
    doInDir(fusepydir, "cp %s ../../.." % " ".join(fusepyfiles))
    print "Building Python SSLCrypto module..."
    doInDir(cryptodir, pythoncmd+" setup.py build_ext --inplace")
    doInDir(cryptodir, "cp %s ../.." % " ".join(cryptofiles))
    open(makedonefile, "w")
    print "--------------------------"
    print "Build appears successful"


def makeInstall():
    if not os.path.isfile(makedonefile):
        print "Please run '%s build' first" % progname
        sys.exit(1)
    import mount
    mntfile = os.path.abspath(mount.__file__).replace(".pyc", ".py")
    import util.pbfs
    pbfsfile = os.path.abspath(util.pbfs.__file__).replace(".pyc", ".py")
    cmds = ["cd %s" % fusedir,
            "make install",
            "cd ..",
            "rm -f /sbin/mount.pbfs",
            "chmod 755 %s" % mntfile,
            "ln -s %s /sbin/mount.pbfs" % mntfile,
            "rm -f /usr/bin/pbfs",
            "chmod 755 %s" % pbfsfile,
            "ln -s %s /usr/bin/pbfs" % pbfsfile
            ]
    print "We will need to execute the following commands as root:", "\n % ".join(['']+cmds)
    print "If you're not already root, you will be prompted for the root password"
    print "(If you feel mistrustful, please audit this make.py script to your satisfaction)"
    cmd = " && ".join(cmds)
    fullcmd = "su -c \"%s\"" % cmd
    #print "want to execute:\n %s" % fullcmd
    ret = sh(fullcmd)
    print "*****************************"
    if ret:
        print "INSTALL FAILED"
        print "got ret = %s" % ret
    else:
        print "Install seems to have worked :)"

    #sh("su -c \"cd %s && make install && cd ../%s && python setup.py install\"" % (fusedir, cryptodir))

def makeClean():
    if os.path.isfile(makedonefile):
        os.unlink(makedonefile)
    cmds = ["rm -f `find . -name \*~` `find . -name \*.pyc` `find . -name \*.so`",
            "cd %s" % fusedir,
            #"make clean",
            "make clean",
            "cd python",
            "rm -rf build fuse.h *.so",
            "cd ../../../../%s" % cryptodir,
            "rm -rf build *.so",
            #"make clean",
            ]
    ret = sh(" && ".join(cmds))
    if ret:
        print "HUH?! '%s clean' failed!?" % progname
        sys.exit(1)

def usage(ret):
    print "Usage: %s build" % progname
    print "          -- builds requisite modules"
    print "       %s install" % progname
    print "          -- sets up PhoneBook to run from this directory"
    print "             (you will be prompted for root password)"
    print
    sys.exit(ret)

def main():
    global argc, argv
    argv = sys.argv
    argc = len(argv)
    if argc == 1:
        print "No option specified"
        usage(1)
    option = argv[1]
    if option == 'build':
        makeBuild()
    elif option == 'install':
        makeInstall()
    elif option == 'clean':
        makeClean()
    else:
        print "Bad option '%s'" % option
        usage(1)

if __name__ == '__main__':
    main()


#@-node:@file make.py
#@-leo

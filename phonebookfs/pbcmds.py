#!/usr/bin/env python
#@+leo-ver=4
#@+node:@file pbcmds.py
#@@first

"""
pbcmds.py

classes for client progs to send commands to PhoneBookFS,
and get responses back.
"""

#@+others
#@+node:imports
import sys, os, time, random, socket
from pdb import set_trace as trace
#@-node:imports
#@+node:globals

# magic pathname, denoting that the client is sending a command
# or receiving a response

cmdFile = "/__cmd"
respFile = "/__resp"

# magic directory name, denoting that the client wants direct
# access to a specific layer

layerDir = "__layers"


argv = sys.argv
argc = len(argv)


lastCmdTime = 0
minTimeBetweenCommands = 1.5
#@-node:globals
#@+node:sendPbCommand
def sendPbCommand(mountpoint, cmdDict=None, **kw):
    """
    This function is the main way of talking to the pb kernel.
    
    What it does is:
       - Encodes a dictionary cmdDict into text
       - sends it to the PhoneBook kernel (writes as special file)
       - reads back the response as special file
       -  decodes the response back into a dict, and returns it
    """

    # wait if it's too soon
    global lastCmdTime
    now = time.time()
    timeSinceLast = now - lastCmdTime
    if timeSinceLast < minTimeBetweenCommands:
        time.sleep(minTimeBetweenCommands - timeSinceLast)
    
    if cmdDict == None:
        cmdDict = kw

    # create some absolute pathnames

    # note that these must be single-use non-repeatable names, in order to
    # defeat caching within the kernel
    fnameCmd = mountpoint + cmdFile + str(time.time()) + str(random.randint(0,9999))
    fnameResp = mountpoint + cmdFile + str(time.time()) + str(random.randint(0,9999))

    #fnameCmd = mountpoint + cmdFile
    #fnameResp = mountpoint + respFile

    # encode the dict
    buf = encodeDict(cmdDict)

    # send the command
    if 0:
        f = file(fnameCmd, "wb")
        f.write(buf)
        f.flush()
        os.fsync(f.fileno())
        f.close()

    #print "pbcmds: opening socket"
    sockfile = os.path.join("/tmp", "pbfs."+(mountpoint.replace("/", "_")))
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(sockfile)
    #print "pbcmds: sending command"
    s.send(buf)
    #print "pbcmds: awaiting response"
    # get the response
    if 0:
        raw = ''
        f = file(fnameResp)
        while 1:
            got = f.read()
            if not got:
                break
            raw += got
        f.close()
    f = s.makefile("rb")
    raw = ''
    while 1:
        got = f.readline()
        if not got:
            time.sleep(0.1)
        #print "got = '%s'" % repr(got)
        raw += got
        if got == "End\n":
            break
    s.close()

    #print "raw='%s'" % raw

    lastCmdTime = time.time()

    # convert into a dict
    try:
        d = decodeDict(raw, "PBResp")
    except:
        return {}

    # done
    return d


#@-node:sendPbCommand
#@+node:escapeField
def escapeField(fld):
    """
    Escapes dodgy characters in field
    """
    fld = str(fld)
    fld = fld.replace("\\", "\\\\")
    fld = fld.replace("\n", "\\n")
    fld = fld.replace("=", "\\=")
    return fld

#@-node:escapeField
#@+node:unescapeField
def unescapeField(fld):
    """
    Unescapes a field
    """
    fld = fld.replace("\\=", "=")
    fld = fld.replace("\\n", "\n")
    fld = fld.replace("\\\\", "\\")
    return fld
#@-node:unescapeField
#@+node:encodeDict
def encodeDict(d=None, hdr="PBcmd", **kw):
    """
    Encodes a dict for sending to PhoneBook kernel
    """
    if d == None:
        d = kw
    buf = hdr + "\n"
    for k,v in d.items():
        k = escapeField(k)
        v = escapeField(v)
        buf += k+"="+v+"\n"
    buf += "End\n"
    return buf

#@-node:encodeDict
#@+node:decodeDict
def decodeDict(raw, hdr='PBcmd'):
    """
    Decodes a raw buffer to a dict
    """
    #print "decodeDict: raw:\n" + raw

    lines = raw.strip().split("\n")
    if lines[0] != hdr:
        print "raw = '%s'" % repr(raw)
        raise Exception("Bad header '%s'" % lines[0])
    if lines[-1] != 'End':
        print "raw = '%s'" % repr(raw)
        raise Exception("Bad footer '%s'" % lines[-1])
    lines = lines[1:-1]
    d = dict([unescapeField(line).split("=",1) for line in lines])

    return d

#@-node:decodeDict
#@+node:makedict
def makedict(*args, **kw):
    if args:
        return dict(*args)
    else:
        return kw

#@-node:makedict
#@+node:usage
def usage(ret=0):
    print "Usage: %s mountpoint command=cmd[,arg1=val1,...]" % argv[0]
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

    if argc == 2:
        print "Sending default 'hello' command"
        cmddict = dict(command="hello")
    else:
        cmddict = dict([arg.split("=",1) for arg in argv[2].split(",")])

    resp = sendPbCommand(mountpoint, **cmddict)

    print repr(resp)
#@-node:main
#@+node:mainline
if __name__ == '__main__':
    main()

#@-node:mainline
#@-others
#@-node:@file pbcmds.py
#@-leo

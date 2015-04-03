#@+leo-ver=4
#@+node:@file pbconfig.py
"""
Configuration settings for PhoneBookFS

Please freely edit these as you see fit
"""

# Minimum amount of random padding to add to a file
minpadding = 2048

# Maximum amount of random padding to add to a file
# Note that for real deniability, you should set this to something
# larger than the largest file in your filesystem

maxpadding = 65536

# Size of files written to the datastore. Any files shorter
# than this will be randomly padded

# increase this size if you are likely to be storing large
# files into the datastore.

# larger sizes cause more wastage, but deliver better speed
# with file I/O

filesize = 16384
#filesize = 256

#@-node:@file pbconfig.py
#@-leo

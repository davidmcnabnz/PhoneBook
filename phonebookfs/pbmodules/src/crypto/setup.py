#@+leo-ver=4
#@+node:@file pbmodules/src/crypto/setup.py
from distutils.core import setup
from distutils.extension import Extension

try:
    raise
    from Pyrex.Distutils import build_ext
    gotPyrex = 1
except:
    gotPyrex = 0

import sys

sslLibs = ['crypto']
extra_link_args = []

if gotPyrex:
    setup(
      name = "SSLCrypto",
      version = '0.1',
      ext_modules=[ 
        Extension("SSLCrypto", ["SSLCrypto.pyx", 'die.c'],
                  libraries=sslLibs,
                  extra_link_args=extra_link_args)
        ],
      cmdclass = {'build_ext': build_ext}
    )
else:
    setup(
      name = "SSLCrypto",
      version = '0.1',
      ext_modules=[ 
        Extension("SSLCrypto", ["SSLCrypto.c", 'die.c'],
                  libraries=sslLibs,
                  extra_link_args=extra_link_args)
        ],
    )
#@-node:@file pbmodules/src/crypto/setup.py
#@-leo

#@+leo-ver=4
#@+node:@file pbmodules/src/crypto/Makefile
# Makefile for SSLCrypto python extension

all:
	@echo "Available targets:"
	@echo "  modules - build the dependencies"
	@echo "  install (root only) - install modules in standard places"


# if the make screws up, you might need to edit the 2 variables
# at the top of the file 'setup.py'.

modules: SSLCrypto.so

install:
	python setup.py install

SSLCrypto.so: SSLCrypto.c die.c
	python setup.py build_ext --inplace

clean:
	rm -rf SSLCrypto.so SSLCrypto.o die.o build

#doco:
#	epydoc -n "FreeMail API" -o doc/classes freemail.py
#@-node:@file pbmodules/src/crypto/Makefile
#@-leo

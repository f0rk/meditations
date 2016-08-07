#!/usr/bin/env bash
# Copyright 2016, Ryan Kelly. All Rights Reserved.

shopt -s globstar

build_path=`realpath build`

cd build

cd ../server

zip "$build_path/meditate.py.zip" meditate.py

# if you need to add things from your virtualenv to the package, look below:
#
#cd ../virtualenv/lib/python2.7/site-packages/
#
#find . -name '*.pyc' -delete
#
#zip "$build_path/submit.py.zip" requests/**

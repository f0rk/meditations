#!/bin/sh
# Copyright 2016, Ryan Kelly.

if [ ! -e virtualenv ]; then
    virtualenv virtualenv
fi

. virtualenv/bin/activate

pip install awscli flask nose2
python setup.py develop

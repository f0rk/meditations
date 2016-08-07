#!/bin/sh
# Copyright 2016, Ryan Kelly. All Rights Reserved.

if [ ! -e virtualenv ]; then
    ./tools/setup.sh
fi

if [ -z "$VIRTUAL_ENV" ]; then
    . virtualenv/bin/activate
fi

export FLASK_DEBUG=1
python tools/serve.py

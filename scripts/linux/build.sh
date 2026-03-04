#!/usr/bin/env bash

# Assumes dependencies are installed.

set -e

export PATH="$PATH:${HOME}/.local/bin"

python_version=3.12

if [ ! -f "/usr/include/python${python_version}/Python.h" ]
then
    echo "Python $python_version headers were not found. Installing."
    sudo apt-get -y install python${python_version}-dev
fi

poetry run poe build_binary

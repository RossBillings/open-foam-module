#!/usr/bin/env bash

# Installs all tools and dependencies required to build:
# 1. Python 3.12
# 2. Python 3.12-dev (Python 3.12 headers, libraries, and development tools)
# 3. pipx
# 4. poetry

# This script assumes a Debian distribution.

set -e

python_version=3.12

install_python() {
    if ! find /etc/apt/ -name "*.list" | xargs cat | grep "^deb.*/deadsnakes/"
    then
        echo "Adding deadsnakes PPA."
        sudo add-apt-repository -y ppa:deadsnakes/ppa
    fi
    sudo apt-get update
    echo "Installing Python $python_version."
    sudo apt-get -y install python$python_version
}

if ! command -v python$python_version >/dev/null 2>&1
then
    echo "Python $python_version was not found on this system. Attempting to install."
    install_python
fi

if ! command -v poetry >/dev/null 2>&1
then
    if ! command -v pipx >/dev/null 2>&1
    then
        echo "Installing pipx."
        sudo apt-get -y install pipx
    fi
    echo "Installing poetry with pipx."
    pipx install poetry
fi

export PATH="$PATH:${HOME}/.local/bin"

echo "Installing dependencies"
poetry install

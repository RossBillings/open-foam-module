#!/usr/bin/env bash

set -e

echo "Removing poetry environment."
poetry env remove $(poetry env info --path | sed 's/.*\///')
echo "Cleaning up build outputs."
rm -r build
rm -r dist

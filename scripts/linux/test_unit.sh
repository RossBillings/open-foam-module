#!/usr/bin/env bash

set -e

echo "Running Tests"
poetry run pytest . -vv --cov=.

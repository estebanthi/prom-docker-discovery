#!/bin/bash

# Ensure script fails if any command fails
set -e

# Export requirements using Poetry
poetry export -f requirements.txt --output requirements.txt --without-hashes

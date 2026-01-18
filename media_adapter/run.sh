#!/bin/bash

# Example wrapper script to run the media adapter

# Ensure we are in the project root
cd "$(dirname "$0")/.."

# Put your default arguments here
PLATFORM="xhs"
KEYWORDS="python,crawler"

echo "Running Media Adapter for platform: $PLATFORM with keywords: $KEYWORDS"
echo "Check README_SETUP.md for more options."

python -m media_adapter.app --platform "$PLATFORM" --keywords "$KEYWORDS" "$@"

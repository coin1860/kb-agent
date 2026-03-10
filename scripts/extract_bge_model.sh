#!/bin/bash

# Define the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
TARGET_DIR="${ROOT_DIR}/models"
SOURCE_DIR="${ROOT_DIR}/docs/image/bge-parts"

# Ensure target directory exists
mkdir -p "${TARGET_DIR}"

echo "Assembling and extracting the model parts..."

# Concatenate all png chunks, decompress, and extract
cat "${SOURCE_DIR}/bge_part_*.png" | xz -d | tar -x -C "${TARGET_DIR}"

if [ $? -eq 0 ]; then
    echo "Extraction successful! The model is restored to: ${TARGET_DIR}/bge-small-zh-v1.5"
    echo "You can now safely delete the ${SOURCE_DIR} directory."
else
    echo "Error: Failed to extract the model."
    exit 1
fi

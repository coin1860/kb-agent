#!/bin/bash

# Define the base directory where this script is located
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
TARGET_DIR="${BASE_DIR}/models"

# Ensure target directory exists
mkdir -p "${TARGET_DIR}"

echo "Assembling and extracting the model parts..."

# Concatenate all png chunks, decompress, and extract
cat "${TARGET_DIR}/bge-parts/bge_part_*.png" | xz -d | tar -x -C "${TARGET_DIR}"

if [ $? -eq 0 ]; then
    echo "Extraction successful! The model is restored to: ${TARGET_DIR}/bge-small-zh-v1.5"
    echo "You can now safely delete the ${TARGET_DIR}/bge-parts/ directory."
else
    echo "Error: Failed to extract the model."
    exit 1
fi

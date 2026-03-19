#!/bin/bash

# Define the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
TARGET_DIR="${ROOT_DIR}/models"
SOURCE_DIR="${ROOT_DIR}/docs/image/bge-parts"

# Ensure target directory exists
mkdir -p "${TARGET_DIR}"

echo "Assembling and extracting the model parts..."

# Concatenate all png chunks, decompress with tar (gzip), and extract
cat "${SOURCE_DIR}"/bge_part_*.png > "${TARGET_DIR}/models.tar.gz"
tar -xzf "${TARGET_DIR}/models.tar.gz" -C "${TARGET_DIR}"
tar_status=$?
rm -f "${TARGET_DIR}/models.tar.gz"

if [ $tar_status -eq 0 ]; then
    echo "Extraction successful! The models are restored to: ${TARGET_DIR}"
    echo "You can now safely delete the ${SOURCE_DIR} directory."
else
    echo "Error: Failed to extract the models."
    exit 1
fi

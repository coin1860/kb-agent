#!/bin/bash
# Define the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
MODEL_DIR="${ROOT_DIR}/models"
OUTPUT_DIR="${ROOT_DIR}/docs/image/bge-parts"

if [ ! -d "$MODEL_DIR" ]; then
    echo "Error: Model directory not found at $MODEL_DIR"
    exit 1
fi

# Ensure output directory exists and is clean
mkdir -p "$OUTPUT_DIR"
rm -f "${OUTPUT_DIR}"/bge_part_*

echo "Compressing and splitting models directory..."
# Use tar with gzip (-czf) and maximize compression
export GZIP="-9"
cd "$MODEL_DIR" || exit 1
tar -czf "${OUTPUT_DIR}/models.tar.gz" .
split -b 99m "${OUTPUT_DIR}/models.tar.gz" "${OUTPUT_DIR}/bge_part_"
rm -f "${OUTPUT_DIR}/models.tar.gz"

# Rename parts to .png for disguise
for f in "${OUTPUT_DIR}"/bge_part_*; do
    if [ "$f" != "${OUTPUT_DIR}/bge_part_*" ]; then
        mv "$f" "${f}.png"
    fi
done

echo "Compression complete. Parts are in $OUTPUT_DIR"

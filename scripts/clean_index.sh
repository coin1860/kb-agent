#!/usr/bin/env bash

# This script safely clears the ChromaDB vector database and all indexed data 
# (Markdown files, summaries, and the knowledge graph) without touching the original source documents.

# Find the config script python path
PYTHON="python3"
if [ -d "lib/python3.11" ]; then
    PYTHON="./bin/python" # If in venv
fi

echo "🔍 Fetching configuration paths..."

# Extract the index path dynamically from kb-agent's configuration
INDEX_PATH=$(PYTHONPATH=src $PYTHON -c "import kb_agent.config as config; print(config.load_settings().index_path)" 2>/dev/null)

if [ -z "$INDEX_PATH" ] || [ "$INDEX_PATH" == "None" ]; then
    echo "❌ Error: Could not determine index_path from kb-agent configuration."
    echo "Please ensure your configuration is valid."
    exit 1
fi

CHROMA_DIR="$INDEX_PATH/.chroma"

echo "==============================================="
echo "🗑️  Cleanup Target Overview:"
echo "   Index Path:  $INDEX_PATH"
echo "   Chroma DB:   $CHROMA_DIR"
echo "==============================================="
echo ""
echo "⚠️  WARNING: This will PERMANENTLY delete all generated indexes and markdown summaries."
echo "   Your original source files (in source_docs_path and archive_path) will NOT be affected."
echo ""
read -p "Are you sure you want to proceed? (y/N) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]
then
    echo "🧹 Starting cleanup..."

    # 1. Delete Chroma Vector Database
    if [ -d "$CHROMA_DIR" ]; then
        echo "   -> Removing ChromaDB directory..."
        rm -rf "$CHROMA_DIR"
    else
        echo "   -> ChromaDB directory not found, skipping."
    fi

    # 2. Delete Markdown Files
    echo "   -> Removing all indexed markdown (*.md) files..."
    find "$INDEX_PATH" -maxdepth 1 -name "*.md" -type f -delete

    # 3. Delete Knowledge Graph cache/JSON
    echo "   -> Removing knowledge graph data..."
    find "$INDEX_PATH" -maxdepth 1 -name "knowledge_graph.json" -type f -delete

    echo "✅ Cleanup complete! Your kb-agent index is now completely fresh."
    echo "   You can now run 'kb-agent index' or use the TUI to re-index your documents."
else
    echo "⛔ Cleanup canceled."
fi

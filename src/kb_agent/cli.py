import argparse
import sys
import os
from pathlib import Path
import kb_agent.config as config
from kb_agent.config import load_settings

def run_indexing():
    # Reload settings to ensure we have latest env vars
    load_settings()
    settings = config.settings

    if not settings:
        print("Error: Settings not configured. Please set KB_AGENT_LLM_API_KEY environment variable.")
        sys.exit(1)

    print(f"Indexing documents from {settings.source_docs_path} to {settings.index_path}...")

    import shutil
    # Ensure index, source and archive paths exist before continuing
    os.makedirs(settings.index_path, exist_ok=True)
    os.makedirs(settings.source_docs_path, exist_ok=True)
    os.makedirs(settings.archive_path, exist_ok=True)

    # Lazy import to avoid early config checks failure
    from kb_agent.processor import Processor
    from kb_agent.connectors.local_file import LocalFileConnector
    from kb_agent.graph.graph_builder import GraphBuilder

    processor = Processor(settings.index_path)
    graph_builder = GraphBuilder(settings.source_docs_path, settings.index_path)

    # Read from SOURCE path
    connector = LocalFileConnector(settings.source_docs_path)

    try:
        all_docs = connector.fetch_all()
    except FileNotFoundError:
        print(f"Source directory {settings.source_docs_path} not found.")
        sys.exit(1)

    count = 0

    for doc in all_docs:
        file_id = doc["id"] # filename
        source_path = doc.get("metadata", {}).get("path")

        # Skip summaries if they somehow exist in source (unlikely unless user copied them back)
        if "-summary.md" in file_id:
            continue

        try:
            print(f"Processing {file_id}...")
            processor.process(doc)
            count += 1
            
            # Archive the file
            if source_path and os.path.exists(source_path):
                dest_path = settings.archive_path / file_id
                # If file already exists in archive, handle it (e.g., overwrite or suffix)
                # Here we just move/overwrite for simplicity as per user request to avoid re-indexing
                shutil.move(source_path, dest_path)
                print(f"Archived {file_id} to {settings.archive_path}")

        except Exception as e:
            print(f"Failed to process {file_id}: {e}")

    # Build Knowledge Graph
    try:
        graph_builder.build_graph()
    except Exception as e:
        print(f"Graph build failed: {e}")

    print(f"Indexing complete. Processed {count} documents.")

def main():
    parser = argparse.ArgumentParser(description="KB Agent CLI")
    parser.add_argument("command", nargs="?", choices=["index", "tui"], default="tui", help="Command to run (default: tui)")

    args = parser.parse_args()

    if args.command == "index":
        run_indexing()
    else:
        # Run TUI
        from kb_agent.tui import KBAgentApp
        app = KBAgentApp()
        app.run()

if __name__ == "__main__":
    main()

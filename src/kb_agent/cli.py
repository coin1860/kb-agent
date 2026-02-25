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

    # Ensure index path exists
    os.makedirs(settings.index_path, exist_ok=True)

    # Lazy import to avoid early config checks failure
    from kb_agent.processor import Processor
    from kb_agent.connectors.local_file import LocalFileConnector

    processor = Processor(settings.index_path)

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

        # Skip summaries if they somehow exist in source (unlikely unless user copied them back)
        if "-summary.md" in file_id:
            continue

        try:
            print(f"Processing {file_id}...")
            processor.process(doc)
            count += 1
        except Exception as e:
            print(f"Failed to process {file_id}: {e}")

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

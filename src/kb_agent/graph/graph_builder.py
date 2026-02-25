import networkx as nx
import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, List
import hashlib
from datetime import datetime

logger = logging.getLogger("kb_agent")

class GraphBuilder:
    def __init__(self, source_path: Path, index_path: Path):
        self.source_path = source_path
        self.index_path = index_path
        self.graph_path = index_path / "knowledge_graph.json"
        self.graph = nx.DiGraph()

        # Regex patterns
        self.jira_link_pattern = re.compile(r'\[([A-Z]+-\d+)\]')
        self.md_link_pattern = re.compile(r'\[.*?\]\((.*?)\)')
        self.wiki_link_pattern = re.compile(r'\[\[(.*?)\]\]')

        self.parent_pattern = re.compile(r'Parent:\s*\[([A-Z]+-\d+)\]', re.IGNORECASE)
        self.clones_pattern = re.compile(r'Clones:\s*\[([A-Z]+-\d+)\]', re.IGNORECASE)
        self.blocks_pattern = re.compile(r'Blocks:\s*\[([A-Z]+-\d+)\]', re.IGNORECASE)

    def build_graph(self):
        """Scans source docs and builds the graph incrementally."""
        logger.info(f"Building Knowledge Graph from {self.source_path}...")

        # Load existing graph to preserve unaffected nodes/edges
        self.load_graph()

        # Track active files to remove deleted ones later
        active_files = set()

        for root, dirs, files in os.walk(self.source_path):
            root_path = Path(root)

            # Add Folder Nodes
            rel_root = root_path.relative_to(self.source_path)
            if str(rel_root) != ".":
                self.graph.add_node(str(rel_root), type="folder", label=rel_root.name)
                parent_dir = rel_root.parent
                if str(parent_dir) != ".":
                     self.graph.add_edge(str(parent_dir), str(rel_root), relation="CONTAINS")

            for file in files:
                if not file.lower().endswith(".md"):
                    continue

                file_path = root_path / file
                rel_path = file_path.relative_to(self.source_path)
                file_id = str(rel_path)
                active_files.add(file_id)

                # Check hash for incremental update
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    current_hash = hashlib.md5(content.encode("utf-8")).hexdigest()

                    # Check if node exists and hash matches
                    if file_id in self.graph.nodes:
                        stored_hash = self.graph.nodes[file_id].get("hash")
                        if stored_hash == current_hash:
                            # logger.debug(f"Skipping unchanged file: {file_id}")
                            continue # No changes, skip parsing

                    # New or modified file
                    logger.info(f"Processing changed/new file: {file_id}")

                    # Remove old edges originating from this file (to clear old links)
                    # We can't easily isolate only "link" edges vs hierarchy edges without attributes
                    # But hierarchy is re-added below. So clearing outgoing is mostly safe IF we re-add folder link.
                    # Safe approach: Clear all outgoing edges from this node.
                    if file_id in self.graph:
                        # list() is needed because we can't iterate while modifying
                        out_edges = list(self.graph.out_edges(file_id))
                        self.graph.remove_edges_from(out_edges)

                    # Update Node
                    self.graph.add_node(file_id, type="file", label=file, hash=current_hash)

                    # Re-add Folder -> File link (Incoming to file, so safe from removal above)
                    if str(rel_root) != ".":
                        self.graph.add_edge(str(rel_root), file_id, relation="CONTAINS")

                    # Parse Content Relations
                    self._extract_relations(file_id, content)

                except Exception as e:
                    logger.warning(f"Failed to parse {file_path} for graph: {e}")

        # Cleanup: Remove nodes representing files that no longer exist
        # We need to be careful not to remove "virtual" nodes (Jira IDs) that are not files
        nodes_to_remove = []
        for node, data in self.graph.nodes(data=True):
            if data.get("type") == "file":
                if node not in active_files:
                    nodes_to_remove.append(node)

        if nodes_to_remove:
            logger.info(f"Removing {len(nodes_to_remove)} deleted files from graph.")
            self.graph.remove_nodes_from(nodes_to_remove)

        self.save_graph()
        logger.info(f"Graph built with {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges.")

    def _extract_relations(self, source_id: str, content: str):
        # 1. Jira Links
        parent_match = self.parent_pattern.search(content)
        if parent_match:
            target_id = parent_match.group(1)
            target_node = self._resolve_node_id(target_id)
            self.graph.add_node(target_node, type="jira_issue")
            self.graph.add_edge(target_node, source_id, relation="PARENT_OF")
            self.graph.add_edge(source_id, target_node, relation="CHILD_OF")

        links = self.jira_link_pattern.findall(content)
        for link in links:
            target_node = self._resolve_node_id(link)
            self.graph.add_node(target_node, type="jira_issue")
            self.graph.add_edge(source_id, target_node, relation="MENTIONS")

        # 2. Internal Links
        md_links = self.md_link_pattern.findall(content)
        for link in md_links:
            target_id = str(Path(link))
            self.graph.add_edge(source_id, target_id, relation="REFERENCES")

    def _resolve_node_id(self, entity_id: str) -> str:
        return entity_id

    def save_graph(self):
        data = nx.node_link_data(self.graph)
        with open(self.graph_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_graph(self):
        if self.graph_path.exists():
            try:
                with open(self.graph_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.graph = nx.node_link_graph(data)
            except Exception as e:
                logger.warning(f"Failed to load existing graph: {e}. Starting fresh.")
                self.graph = nx.DiGraph()
        else:
            self.graph = nx.DiGraph()

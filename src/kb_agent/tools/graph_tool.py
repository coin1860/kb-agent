from kb_agent.graph.graph_builder import GraphBuilder
from kb_agent.config import settings
from typing import List, Dict, Any
import networkx as nx
import logging

logger = logging.getLogger("kb_agent")

class GraphTool:
    def __init__(self):
        if settings:
            self.builder = GraphBuilder(settings.source_docs_path, settings.index_path)
            self.builder.load_graph()
            self.graph = self.builder.graph
        else:
            self.graph = nx.DiGraph()

    def get_related_nodes(self, entity_id: str, max_depth: int = 1) -> List[Dict[str, Any]]:
        """
        Returns related nodes for a given entity.
        Supports fuzzy matching if exact node not found.
        """
        if not self.graph:
            return []

        # 1. Find target node
        target = None
        if entity_id in self.graph:
            target = entity_id
        else:
            # Try appending .md
            if f"{entity_id}.md" in self.graph:
                target = f"{entity_id}.md"
            # Try finding matches by label
            else:
                for node, data in self.graph.nodes(data=True):
                    if entity_id.lower() in str(node).lower():
                        target = node
                        break

        if not target:
            return []

        results = []
        # Get neighbors (successors and predecessors)
        # For undirected relationship semantics, we look at both

        # Outgoing edges
        for neighbor in self.graph.successors(target):
            edge_data = self.graph.get_edge_data(target, neighbor)
            results.append({
                "node": neighbor,
                "type": self.graph.nodes[neighbor].get("type", "unknown"),
                "relation": edge_data.get("relation", "related_to"),
                "direction": "out"
            })

        # Incoming edges
        for neighbor in self.graph.predecessors(target):
            edge_data = self.graph.get_edge_data(neighbor, target)
            results.append({
                "node": neighbor,
                "type": self.graph.nodes[neighbor].get("type", "unknown"),
                "relation": edge_data.get("relation", "related_to"),
                "direction": "in"
            })

        return results

    def find_path(self, start: str, end: str) -> List[str]:
        try:
            return nx.shortest_path(self.graph, start, end)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

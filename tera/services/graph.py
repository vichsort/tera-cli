from typing import Dict, List, Optional, Set, Tuple
import re

from tera.domain.models import TeraSchema
from tera.domain.graph import ApiGraph, GraphEdge, GraphNode


class GraphService:
    """
    Analyzes an API schema and builds an architectural dependency graph
    between endpoints based on resource hierarchy, entity life-cycle,
    and sub-resource relationships.
    """

    def build_graph(self, schema: TeraSchema) -> ApiGraph:
        nodes: List[GraphNode] = []
        node_map: Dict[Tuple[str, str], GraphNode] = {}  # (method, path) -> GraphNode

        for ep in schema.endpoints:
            node_id = f"{ep.method}_{ep.path}"
            # Infer tag if not present based on first path segment
            tag = ep.tag
            if not tag:
                segments = [s for s in ep.path.strip("/").split("/") if s and not s.startswith("{")]
                tag = segments[0].capitalize() if segments else "General"

            node = GraphNode(
                id=node_id,
                method=ep.method,
                path=ep.path,
                summary=ep.summary,
                tag=tag,
            )
            nodes.append(node)
            node_map[ep.key] = node

        edges: List[GraphEdge] = []
        added_edge_keys: Set[Tuple[str, str, Optional[str]]] = set()

        def add_edge(src_id: str, tgt_id: str, label: Optional[str]) -> None:
            if src_id == tgt_id:
                return
            key = (src_id, tgt_id, label)
            if key not in added_edge_keys:
                added_edge_keys.add(key)
                edges.append(GraphEdge(source=src_id, target=tgt_id, label=label))

        # 1. Detect CRUD life-cycle: POST collection -> GET/PUT/PATCH/DELETE item
        for ep in schema.endpoints:
            if ep.method == "POST":
                # Check for item endpoints that extend this path with a single parameter
                # e.g., /users -> /users/{id} or /users/{user_id}
                clean_base = ep.path.rstrip("/")
                item_pattern = re.compile(rf"^{re.escape(clean_base)}/\{{([^/]+)\}}$")

                for other in schema.endpoints:
                    m = item_pattern.match(other.path)
                    if m:
                        param_name = m.group(1)
                        src_node = node_map.get(ep.key)
                        tgt_node = node_map.get(other.key)
                        if src_node and tgt_node:
                            add_edge(src_node.id, tgt_node.id, f"creates {{{param_name}}}")

            # 2. Detect sub-resources:
            # e.g., /users/{id} -> /users/{id}/orders
            for other in schema.endpoints:
                if ep.path != other.path and other.path.startswith(ep.path + "/"):
                    suffix = other.path[len(ep.path) + 1 :]
                    # Subresource must not be an item identifier like {id}
                    if not suffix.startswith("{"):
                        if ep.method in ("GET", "POST"):
                            sub_label = f"subresource /{suffix.split('/')[0]}"
                            src_node = node_map.get(ep.key)
                            tgt_node = node_map.get(other.key)
                            if src_node and tgt_node:
                                add_edge(src_node.id, tgt_node.id, sub_label)

        # 3. If an endpoint is completely isolated within its tag, link collection GET to item GET
        for ep in schema.endpoints:
            if ep.method == "GET" and not "{" in ep.path:
                clean_base = ep.path.rstrip("/")
                for other in schema.endpoints:
                    if other.method == "GET" and "{" in other.path and other.path.startswith(clean_base + "/"):
                        src_node = node_map.get(ep.key)
                        tgt_node = node_map.get(other.key)
                        if src_node and tgt_node:
                            add_edge(src_node.id, tgt_node.id, "item of")

        return ApiGraph(nodes=nodes, edges=edges)

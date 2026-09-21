from typing import List, Optional, Dict, Literal
import re
from pydantic import BaseModel, ConfigDict, Field


class GraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    method: str
    path: str
    summary: str
    tag: Optional[str] = None


class GraphEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    label: Optional[str] = None


class ApiGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: List[GraphNode] = Field(default_factory=list[GraphNode])
    edges: List[GraphEdge] = Field(default_factory=list[GraphEdge])

    def to_mermaid(self, direction: Literal["TD", "LR"] = "TD") -> str:
        lines: List[str] = [f"flowchart {direction}"]

        # Group nodes by tag
        by_tag: Dict[str, List[GraphNode]] = {}
        untagged: List[GraphNode] = []

        for node in self.nodes:
            if node.tag:
                by_tag.setdefault(node.tag, []).append(node)
            else:
                untagged.append(node)

        # Render tagged subgraphs
        for tag, tag_nodes in sorted(by_tag.items()):
            subgraph_id = "sg_" + re.sub(r"[^a-zA-Z0-9_]", "_", tag)
            clean_tag = tag.replace('"', '\\"')
            lines.append(f'  subgraph {subgraph_id} ["{clean_tag}"]')
            for n in tag_nodes:
                nid = self._sanitize_id(n.id)
                lines.append(f'    {nid}["{n.method} {n.path}"]')
            lines.append("  end")

        # Render untagged nodes
        for n in untagged:
            nid = self._sanitize_id(n.id)
            lines.append(f'  {nid}["{n.method} {n.path}"]')

        # Render edges
        for edge in self.edges:
            src = self._sanitize_id(edge.source)
            tgt = self._sanitize_id(edge.target)
            if edge.label:
                clean_label = edge.label.replace('"', "'")
                lines.append(f"  {src} -->|{clean_label}| {tgt}")
            else:
                lines.append(f"  {src} --> {tgt}")

        return "\n".join(lines)

    @staticmethod
    def _sanitize_id(raw_id: str) -> str:
        clean = re.sub(r"[^a-zA-Z0-9_]", "_", raw_id)
        if clean and clean[0].isdigit():
            clean = f"n_{clean}"
        return clean or "node"

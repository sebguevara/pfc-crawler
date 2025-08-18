from __future__ import annotations
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END
from app.services.retrieval import kb_search

class RetrievalState(TypedDict):
    question: str
    k: int
    results: List[Dict[str, Any]]

def retrieve_node(state: RetrievalState) -> RetrievalState:
    q = state["question"]
    k = int(state.get("k", 5) or 5)
    out = kb_search(q, k)
    return {**state, "results": out}

# Construimos el grafo de 1 paso
graph = StateGraph(RetrievalState)
graph.add_node("retrieve", retrieve_node)
graph.set_entry_point("retrieve")
graph.add_edge("retrieve", END)

retrieval_app = graph.compile()

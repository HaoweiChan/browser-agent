"""Callback-driven canonical browser graph (ADR-046)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .canonical_contract import NODES, validate_state


class CanonicalState(TypedDict, total=False):
    runtime: object
    result: dict
    context: dict
    mode: str
    node: str
    route: str
    status: str
    verifier: dict
    retry: dict
    budgets: dict
    evidence: list[dict]
    nodes: list[str]
    routes: list[str]


NodeCallback = Callable[[CanonicalState], Awaitable[dict]]


class CanonicalCallbacks(TypedDict):
    observe: NodeCallback
    route: NodeCallback
    evidence: NodeCallback
    plan: NodeCallback
    act: NodeCallback
    evaluate: NodeCallback
    decide: NodeCallback


_NEXT_ROUTE = dict(zip(NODES[:-1], NODES[1:]))
_TRACE_KEYS = {"node", "nodes", "routes"}


def _trace(state: CanonicalState, node: str, route: str) -> tuple[list[str], list[str]]:
    nodes, routes = state.get("nodes", []), state.get("routes", [])
    if not (isinstance(nodes, list) and all(isinstance(value, str) for value in nodes)
            and isinstance(routes, list) and all(isinstance(value, str) for value in routes)):
        raise ValueError("invalid canonical graph trace")
    return [*nodes, node], [*routes, route]


def _node(name: str, callback: NodeCallback):
    async def run(state: CanonicalState) -> CanonicalState:
        delta = await callback(state)
        if not isinstance(delta, dict):
            raise TypeError(f"canonical {name} callback must return a dict delta")
        if blocked := _TRACE_KEYS & delta.keys():
            raise ValueError(f"canonical {name} callback cannot set {sorted(blocked)}")
        candidate = {**state, **delta, "node": name}
        if name != "decide":
            if "route" in delta and delta["route"] != _NEXT_ROUTE[name]:
                raise ValueError(f"invalid canonical {name} callback route")
            candidate["route"] = _NEXT_ROUTE[name]
        errors = validate_state(candidate)
        if errors:
            raise ValueError(f"invalid canonical {name} callback state: {', '.join(errors)}")
        nodes, routes = _trace(state, name, candidate["route"])
        return {**candidate, "nodes": nodes, "routes": routes}

    return run


def _after_decide(state: CanonicalState) -> str:
    return "plan" if state["route"] == "plan" else END


def build_graph(callbacks: Mapping[str, NodeCallback]):
    missing = [name for name in NODES if not callable(callbacks.get(name))]
    if missing:
        raise TypeError(f"missing canonical callbacks: {', '.join(missing)}")
    graph = StateGraph(CanonicalState)
    for name in NODES:
        graph.add_node(name, _node(name, callbacks[name]))
    graph.add_edge(START, "observe")
    for source, target in _NEXT_ROUTE.items():
        graph.add_edge(source, target)
    graph.add_conditional_edges("decide", _after_decide, {"plan": "plan", END: END})
    return graph.compile()


async def run(state: CanonicalState, callbacks: CanonicalCallbacks) -> CanonicalState:
    """Run injected boundaries through the one canonical graph."""
    return await build_graph(callbacks).ainvoke(state)

"""Bounded canonical-node model policy (ADR-048).

The legacy planner/judge keep their historical call paths.  Canonical nodes use
this one small boundary so routes, frozen-price checks, cache identity, spend,
and provider attribution cannot drift apart.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import time
import urllib.request
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Awaitable, Callable

from .planner import (DEFAULT_MODEL, FALLBACK_MODEL, OPENROUTER_URL, SYSTEM,
                      PlanError, build_user, parse_plan)

POLICY_VERSION = "m51-v1"
FLASH_MODEL = "deepseek/deepseek-v4-flash-0731"
PRO_MODEL = DEFAULT_MODEL
MINI_MODEL = FALLBACK_MODEL

# This is the production-safe projection of the frozen label snapshot.  The
# eval checks compare it with evals/labels/openrouter-models-20260820.json;
# production cannot import evals/ because it is excluded from the image.
FROZEN_PRICES = {
    PRO_MODEL: (0.0000016, 0.0000032),
    FLASH_MODEL: (0.00000014, 0.00000028),
    MINI_MODEL: (0.00000025, 0.000002),
}


@dataclass(frozen=True)
class NodePolicy:
    trigger: str
    route: tuple[str, ...]
    max_calls: int
    max_output_tokens: int
    max_input_chars: int
    max_tokens: int
    max_usd: float
    cache_namespace: str
    access_required: bool
    authority: str
    enabled: bool = True
    disabled_reason: str | None = None


# The only canonical-node routes.  An empty vision route is intentional: the
# frozen evidence names no exact Flash Vision model and does not assert that
# Flash accepts images.  GPT-5 mini is retained as the frozen fallback model,
# but cannot make an unvetted primary route executable.
NODE_POLICY = {
    "evidence": NodePolicy(
        trigger="no deterministic cited evidence (reserved; disabled in M51)",
        route=(FLASH_MODEL,), max_calls=1, max_output_tokens=800, max_input_chars=20_000,
        max_tokens=800, max_usd=0.005, cache_namespace="m51-evidence-v1",
        access_required=True, authority="advisory", enabled=False,
        disabled_reason="M51 deterministic evidence is sufficient; no safe text-assistance input"),
    "plan": NodePolicy(
        trigger="canonical plan", route=(PRO_MODEL, MINI_MODEL), max_calls=2,
        max_output_tokens=2000, max_input_chars=50_000, max_tokens=4000, max_usd=0.05,
        cache_namespace="m51-plan-v1", access_required=True,
        authority="proposal"),
    "vision": NodePolicy(
        trigger="experimental visual ambiguity", route=(), max_calls=1,
        max_output_tokens=800, max_input_chars=20_000, max_tokens=800, max_usd=0.01,
        cache_namespace="m51-vision-v1", access_required=True,
        authority="advisory", enabled=False,
        disabled_reason="no exact price-vetted Flash Vision model in frozen snapshot; GPT-5 mini fallback retained but cannot enable an unvetted route"),
    "critic": NodePolicy(
        trigger="deterministic semantic ambiguity only", route=(MINI_MODEL,),
        max_calls=1, max_output_tokens=300, max_input_chars=12_000, max_tokens=300, max_usd=0.005,
        cache_namespace="m51-critic-v1", access_required=True,
        authority="advisory"),
}


class PolicyError(RuntimeError):
    """A classified boundary failure: never a silent fallback or publish."""

    def __init__(self, message: str, usage: dict | None = None):
        super().__init__(message)
        self.usage = usage or {"llm_tokens": 0, "llm_usd": 0.0}


def _price_allowed(model: str) -> bool:
    price = FROZEN_PRICES.get(model)
    ceiling = FROZEN_PRICES[PRO_MODEL]
    return bool(price and price[0] <= ceiling[0] and price[1] <= ceiling[1])


def policy_for(node: str) -> NodePolicy:
    try:
        policy = NODE_POLICY[node]
    except KeyError as exc:
        raise PolicyError(f"unknown canonical model node: {node}") from exc
    if any(not _price_allowed(model) for model in policy.route):
        raise PolicyError(f"canonical {node} route exceeds frozen price ceiling")
    return policy


def _cache_key(node: str, policy: NodePolicy, messages: list[dict], schema_version: str) -> str:
    blob = json.dumps([POLICY_VERSION, policy.cache_namespace, node, list(policy.route), messages, schema_version],
                      sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def semantic_ambiguity(verdict: dict | None) -> bool:
    """The only critic trigger: an explicit deterministic ambiguity marker.

    Ordinary verifier FAIL is not ambiguous and never calls a critic.  M51 has
    no producer for this marker yet, so the production seam is intentionally
    dormant until a deterministic evidence classifier supplies one.
    """
    return bool(isinstance(verdict, dict) and verdict.get("verdict") == "FAIL"
                and str(verdict.get("reason", "")).startswith("ambiguous semantic evidence:"))


Transport = Callable[[dict], Awaitable[dict]]


def canonical_plan_route(model: str = PRO_MODEL, fallback: bool = True) -> tuple[str, ...]:
    """The only public canonical planning selections; no ignored override."""
    if model == PRO_MODEL:
        return (PRO_MODEL, MINI_MODEL) if fallback else (PRO_MODEL,)
    if model == MINI_MODEL:
        return (MINI_MODEL,)
    raise PolicyError(f"canonical plan model blocked: {model}")


CANONICAL_PLAN_MODELS = (PRO_MODEL, MINI_MODEL)


def _cache_path() -> Path:
    return Path(__file__).resolve().parents[2] / "runs" / "canonical_policy_cache.json"


def _cache_load() -> dict:
    try:
        loaded = json.loads(_cache_path().read_text())
        return loaded if isinstance(loaded, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _cache_save(cache: dict) -> None:
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache))


async def _openrouter_transport(payload: dict) -> dict:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise PolicyError("OPENROUTER_API_KEY is not set")

    def post():
        req = urllib.request.Request(
            OPENROUTER_URL, data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.load(response)

    return await asyncio.to_thread(post)


class PolicyBoundary:
    """One injectable request/cache/accounting boundary for canonical nodes."""

    def __init__(self, transport: Transport | None = None, cache: dict | None = None):
        self.transport = transport or _openrouter_transport
        self.cache = cache if cache is not None else _cache_load()
        self.persist_cache = cache is None
        self.spent: dict[str, dict] = {}
        self.node_calls: list[dict] = []

    def _spent(self, node: str) -> dict:
        return self.spent.setdefault(node, {"calls": 0, "tokens": 0, "usd": 0.0})

    def _before_call(self, node: str, policy: NodePolicy) -> None:
        spent = self._spent(node)
        if spent["calls"] >= policy.max_calls:
            raise PolicyError(f"canonical {node} budget exhausted: calls")
        # Do not start a request whose full configured output cannot fit.  The
        # provider reports total tokens only after billing, so a one-token
        # remainder is not authority for another 2,000-token request.
        if spent["tokens"] + policy.max_output_tokens > policy.max_tokens:
            raise PolicyError(f"canonical {node} budget exhausted: tokens")
        output_usd = policy.max_output_tokens * max(
            FROZEN_PRICES[model][1] for model in policy.route)
        if spent["usd"] + output_usd > policy.max_usd:
            raise PolicyError(f"canonical {node} budget exhausted: usd")

    def _record(self, *, node: str, route: tuple[str, ...], served_model: str | None,
                tokens: int, usd: float, latency_ms: int, cached: bool, outcome: str) -> dict:
        record = {"node": node, "requested_route": list(route), "served_model": served_model,
                  "tokens": tokens, "usd": usd, "latency_ms": latency_ms,
                  "cached": cached, "outcome": outcome}
        self.node_calls.append(record)
        return record

    def mark_last(self, node: str, outcome: str) -> None:
        """A schema parser can reject a completed response after this boundary."""
        for record in reversed(self.node_calls):
            if record["node"] == node:
                record["outcome"] = outcome
                return

    def evict(self, node: str, messages: list[dict], schema_version: str,
              route: tuple[str, ...] | None = None) -> None:
        policy = policy_for(node)
        if route is not None:
            policy = replace(policy, route=route)
        self.cache.pop(_cache_key(node, policy, messages, schema_version), None)
        if self.persist_cache:
            try:
                _cache_save(self.cache)
            except OSError:
                pass

    async def call(self, node: str, messages: list[dict], schema_version: str, *,
                   verified_access: bool, route: tuple[str, ...] | None = None) -> tuple[str, dict]:
        policy = policy_for(node)
        if route is not None:
            frozen_route = policy.route
            policy = replace(policy, route=route)
            if (not policy.route or any(model not in frozen_route for model in policy.route)
                    or any(not _price_allowed(model) for model in policy.route)):
                raise PolicyError(f"canonical {node} route exceeds frozen price ceiling")
        if policy.access_required and not verified_access:
            self._record(node=node, route=policy.route, served_model=None, tokens=0, usd=0.0,
                         latency_ms=0, cached=False, outcome="access_refused")
            raise PolicyError(f"canonical {node} requires verified LLM access")
        if not policy.enabled:
            self._record(node=node, route=policy.route, served_model=None, tokens=0, usd=0.0,
                         latency_ms=0, cached=False, outcome="disabled")
            raise PolicyError(f"canonical {node} disabled: {policy.disabled_reason}")
        try:
            self._before_call(node, policy)
        except PolicyError:
            self._record(node=node, route=policy.route, served_model=None, tokens=0, usd=0.0,
                         latency_ms=0, cached=False, outcome="budget_refused")
            raise
        if len(json.dumps(messages, ensure_ascii=False, separators=(",", ":"))) > policy.max_input_chars:
            self._record(node=node, route=policy.route, served_model=None, tokens=0, usd=0.0,
                         latency_ms=0, cached=False, outcome="input_refused")
            raise PolicyError(f"canonical {node} input exceeds {policy.max_input_chars} chars")
        key = _cache_key(node, policy, messages, schema_version)
        cached = self.cache.get(key)
        if isinstance(cached, dict):
            content, model = cached.get("content"), cached.get("served_model")
            if isinstance(content, str) and isinstance(model, str) and model in policy.route and _price_allowed(model):
                telemetry = self._record(node=node, route=policy.route, served_model=model,
                                         tokens=0, usd=0.0, latency_ms=0, cached=True, outcome="ok")
                return content, telemetry
            # Corrupt/untrusted cache is a miss. It never certifies a response.
            self.cache.pop(key, None)
        payload = {"models": list(policy.route), "temperature": 0,
                   "max_tokens": policy.max_output_tokens, "messages": messages,
                   "usage": {"include": True}}
        started = time.monotonic()
        try:
            data = await self.transport(payload)
        except Exception as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            self._spent(node)["calls"] += 1
            self._record(node=node, route=policy.route, served_model=None, tokens=0, usd=0.0,
                         latency_ms=latency_ms, cached=False, outcome="transport_failure")
            raise PolicyError(f"canonical {node} transport failure: {type(exc).__name__}: {exc}") from exc
        latency_ms = int((time.monotonic() - started) * 1000)
        model = data.get("model") if isinstance(data, dict) else None
        usage = data.get("usage") if isinstance(data, dict) else None

        def invalid_accounting() -> None:
            self._spent(node)["calls"] += 1
            self._record(node=node, route=policy.route,
                         served_model=model if isinstance(model, str) else None,
                         tokens=0, usd=0.0, latency_ms=latency_ms,
                         cached=False, outcome="invalid_accounting")
            raise PolicyError(f"canonical {node} invalid provider accounting")

        if not isinstance(usage, dict):
            invalid_accounting()
        raw_tokens = usage.get("total_tokens")
        raw_usd = usage.get("cost")
        try:
            if isinstance(raw_tokens, bool):
                raise ValueError("boolean token count")
            if isinstance(raw_tokens, int):
                tokens = raw_tokens
            elif isinstance(raw_tokens, str) and raw_tokens.isdigit():
                tokens = int(raw_tokens)
            else:
                raise ValueError("token count must be an integer")
            usd = float(raw_usd)
        except (TypeError, ValueError):
            invalid_accounting()
        if tokens < 0 or not math.isfinite(usd) or usd < 0:
            invalid_accounting()
        spent = self._spent(node)
        spent["calls"] += 1
        spent["tokens"] += tokens
        spent["usd"] += usd
        billed = {"llm_tokens": tokens, "llm_usd": usd}
        if not isinstance(data, dict) or data.get("error"):
            self._record(node=node, route=policy.route, served_model=model if isinstance(model, str) else None,
                         tokens=tokens, usd=usd, latency_ms=latency_ms, cached=False, outcome="provider_failure")
            raise PolicyError(f"canonical {node} provider failure: {data.get('error') if isinstance(data, dict) else 'unreadable response'}", billed)
        if not isinstance(model, str) or model not in policy.route or not _price_allowed(model):
            self._record(node=node, route=policy.route, served_model=model if isinstance(model, str) else None,
                         tokens=tokens, usd=usd, latency_ms=latency_ms, cached=False, outcome="served_model_refused")
            raise PolicyError(f"canonical {node} refused unapproved served model: {model!r}", billed)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            self._record(node=node, route=policy.route, served_model=model, tokens=tokens, usd=usd,
                         latency_ms=latency_ms, cached=False, outcome="unreadable_response")
            raise PolicyError(f"canonical {node} unreadable provider response", billed) from exc
        if not isinstance(content, str):
            self._record(node=node, route=policy.route, served_model=model, tokens=tokens, usd=usd,
                         latency_ms=latency_ms, cached=False, outcome="invalid_accounting")
            raise PolicyError(f"canonical {node} invalid provider accounting", billed)
        if spent["tokens"] > policy.max_tokens or spent["usd"] > policy.max_usd:
            self._record(node=node, route=policy.route, served_model=model, tokens=tokens, usd=usd,
                         latency_ms=latency_ms, cached=False, outcome="budget_exceeded")
            raise PolicyError(f"canonical {node} budget exceeded by provider response", billed)
        self.cache[key] = {"content": content, "served_model": model}
        outcome = "ok"
        if self.persist_cache:
            try:
                _cache_save(self.cache)
            except OSError:
                # Caching saves money but must never erase a valid, billed
                # completion from telemetry or aggregate accounting.
                outcome = "ok_cache_write_failed"
        telemetry = self._record(node=node, route=policy.route, served_model=model, tokens=tokens,
                                 usd=usd, latency_ms=latency_ms, cached=False, outcome=outcome)
        return content, telemetry


def canonical_live_planner(*, verified_access: bool, model: str = PRO_MODEL,
                           fallback: bool = True, boundary: PolicyBoundary | None = None):
    """Planner-shaped adapter used only by the public canonical runtime."""
    if not verified_access:
        raise PolicyError("canonical plan requires verified LLM access")
    if boundary is None:
        if not os.environ.get("OPENROUTER_API_KEY"):
            raise PolicyError("OPENROUTER_API_KEY is not set")
        boundary = PolicyBoundary()
    route = canonical_plan_route(model, fallback)

    async def plan(task: str, url: str | None, observation: dict | None = None, note: str | None = None):
        messages = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": build_user(task, url, observation, note)}]
        try:
            content, telemetry = await boundary.call("plan", messages, "planner-json-v1",
                                                     verified_access=verified_access, route=route)
            steps = parse_plan(content)
        except PlanError as exc:
            boundary.mark_last("plan", "parse_failure")
            boundary.evict("plan", messages, "planner-json-v1", route)
            if "telemetry" in locals():
                exc.usage = {"llm_tokens": telemetry["tokens"], "llm_usd": telemetry["usd"]}
            raise
        except PolicyError as exc:
            raise PlanError(str(exc), exc.usage) from exc
        return steps, {"llm_tokens": telemetry["tokens"], "llm_usd": telemetry["usd"],
                       "cached": telemetry["cached"]}

    plan.node_policy_boundary = boundary
    return plan


def node_calls_for(planner) -> list[dict]:
    boundary = getattr(planner, "node_policy_boundary", None)
    return list(getattr(boundary, "node_calls", []))

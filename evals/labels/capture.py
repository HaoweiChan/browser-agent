"""M7 capture harness — one-shot, not a suite (docs/evals/evaluation-methodology.md,
"Verifier accuracy estimation").

Runs a fixed list of (task, fixture-or-live URL, hand-written stub plan) through
the SAME agent path the eval adapter uses (`eval_adapter._run_agent`, the same
`stub_planner`), and appends one JSON line to verifier-sample.jsonl for every
run whose trace reached the runtime `verify()` call inside agent.run_task —
i.e. `result["verdict"] is not None`. Runs that die in the executor (empty
extraction, absent anchor, ambiguous locate, ...) never get a verdict and are
correctly excluded: that is the population `verify()` is ever actually judged
on at runtime, since `run_task`'s own closing `verify(...)` call passes NO `expect`.

Fixture runs (source="fixture") are deterministic replays against the fixture
server on loopback. Live runs (source="live") hit books.toscrape.com and
news.ycombinator.com; both are frozen-ish public sandboxes, but a live re-run
of this script may still disagree with the committed JSONL if the site drifts
— the committed file, not a re-run, is the frozen artifact M7 is measured on.

Does NOT add "label"/"label_reason"/"labeled_from" — those are added by hand
after reading each record's answer/trace/extractions against the task.

REFUSES TO OVERWRITE `verifier-sample.jsonl`. Those hand labels are the one
artifact in this milestone no code can regenerate; a plain `"w"` open here
used to truncate the file silently on every re-run. If the output already
exists, this writes `verifier-sample.new.jsonl` next to it instead — diff and
hand-merge, never let this script touch the labeled file directly.

`runtime_verdict_at_capture` is frozen at the moment this script ran, against
whatever `verifier.py` was at the time — a historical snapshot, never ground
truth. It predates `not_a_dump`, so old records (including the two probe-#5
dumps) show it as PASS with no `not_a_dump` key. Grading never reads this
field: `_run_verifier_labels_case` recomputes `verify()` fresh against the
current `verifier.py` on every replay.
"""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.browser.eval_adapter import _base_url, _post, _run_agent, _subst  # noqa: E402
from src.browser.planner import stub_planner  # noqa: E402

OUT = Path(__file__).parent / "verifier-sample.jsonl"

BOOKS_TRAVEL = "https://books.toscrape.com/catalogue/category/books/travel_2/index.html"
HN_ITEM1 = "https://news.ycombinator.com/item?id=1"
NOAH = "Full Moon over Noah’s Ark: An Odyssey to Mount Ararat and Beyond"

RECORDS = [
    # --- fixture, correct -------------------------------------------------
    dict(id="tc1-shop-price", source="fixture", fixture="shop-lamp-std.html",
         task="What is the price of the Aurora Desk Lamp on this page?",
         stub_plan=[{"action": "extract", "target": {"role": "group", "name": "Price"}, "anchor": "LAMP-STD"}]),
    dict(id="tc2-shop-search", source="fixture", fixture="shop.html",
         task="Search the catalogue for 'Meridian' and name the product you find.",
         stub_plan=[
             {"action": "fill", "target": {"role": "searchbox", "name": "Search products"}, "value": "Meridian",
              "expected_state": None},
             {"action": "click", "target": {"role": "button", "name": "Search"},
              "expected_state": {"text_visible": '1 result(s) for "meridian"'}},
             {"action": "extract", "target": {"role": "link", "index": 0}, "anchor": "Meridian"}]),
    dict(id="tc4-shop-sort-cheapest", source="fixture", fixture="shop.html",
         task="Sort the catalogue by price, low to high, and name the cheapest product.",
         stub_plan=[
             {"action": "click", "target": {"role": "button", "name": "Sort by price (low to high)"},
              "expected_state": {"text_visible": "Sorted by price (low to high)"}},
             {"action": "extract", "target": {"role": "link", "index": 0}}]),
    dict(id="near-prefers-the-container", source="fixture", fixture="shop.html",
         task="Which catalogue row costs $24.50?",
         stub_plan=[{"action": "extract", "target": {"role": "listitem", "near": "$24.50"}, "anchor": "$24.50"}]),
    dict(id="near-excludes-its-own-anchor", source="fixture", fixture="shop-lamp-spec.html",
         task="What is the UPC product code of this lamp?",
         stub_plan=[{"action": "extract", "target": {"role": "cell", "near": "UPC"}, "anchor": "Aurora Desk Lamp"}]),
    dict(id="tc5-forms-submit", source="fixture", fixture="forms.html",
         task=("Send an enquiry from Ada Lovelace (ada@example.com) asking whether the "
               "Aurora lamp is dimmable, and report the reference number."),
         stub_plan=[
             {"action": "fill", "target": {"role": "textbox", "name": "Full name"}, "value": "Ada Lovelace"},
             {"action": "fill", "target": {"role": "textbox", "name": "Email"}, "value": "ada@example.com"},
             {"action": "fill", "target": {"role": "textbox", "name": "Message"}, "value": "Is the Aurora lamp dimmable?"},
             {"action": "click", "target": {"role": "button", "name": "Submit enquiry"},
              "expected_state": {"text_visible": "Enquiry received"}},
             {"action": "extract", "target": {"role": "group", "name": "Reference"}, "anchor": "Ada Lovelace"}]),

    # --- fixture, wrong (still reaches verify()) ---------------------------
    dict(id="trap-near-miss-entity", source="fixture", fixture="shop.html",
         task="What is the price of the Aurora Desk Lamp?",
         stub_plan=[
             {"action": "click", "target": {"role": "link", "name": "Aurora Desk Lamp Pro"},
              "expected_state": {"url_contains": "shop-lamp-pro"}},
             {"action": "extract", "target": {"role": "group", "name": "Price"}, "anchor": "Aurora Desk Lamp"}]),
    dict(id="trap-wrong-field", source="fixture", fixture="shop-lamp-std.html",
         task="What is the SKU of the Aurora Desk Lamp?",
         stub_plan=[{"action": "extract", "target": {"role": "group", "name": "Material"}, "anchor": "LAMP-STD"}]),
    dict(id="trap-unsorted-cheapest", source="fixture", fixture="shop.html",
         task="Sort the catalogue by price, low to high, and name the cheapest product.",
         stub_plan=[{"action": "extract", "target": {"role": "link", "index": 0}}]),
    dict(id="trap-search-not-executed", source="fixture", fixture="shop.html",
         task="Search the catalogue for 'Meridian' and name the product you find.",
         stub_plan=[
             {"action": "fill", "target": {"role": "searchbox", "name": "Search products"}, "value": "Meridian"},
             {"action": "extract", "target": {"role": "link", "index": 0}, "anchor": "Meridian"}]),
    dict(id="trap-form-not-submitted", source="fixture", fixture="forms.html",
         task="Send an enquiry from Grace Hopper (grace@example.com) about bulk orders and confirm it was sent.",
         stub_plan=[
             {"action": "fill", "target": {"role": "textbox", "name": "Full name"}, "value": "Grace Hopper"},
             {"action": "fill", "target": {"role": "textbox", "name": "Email"}, "value": "grace@example.com"},
             {"action": "fill", "target": {"role": "textbox", "name": "Message"}, "value": "Do you take bulk orders?"},
             {"action": "extract", "target": {"role": "heading", "name": "Contact Nimbus Shop"}}]),
    dict(id="trap-wrong-cell-total", source="fixture", fixture="shop-order.html",
         task="What is the total on this order?",
         stub_plan=[{"action": "extract", "target": {"role": "cell", "index": 1}, "anchor": "NIM-4417"}]),

    # --- fixture, probe-#5 (page dump instead of one answer) ---------------
    dict(id="probe5-shop-listing-dump", source="fixture", fixture="shop.html",
         task="Which product is the cheapest, and what is its price?",
         stub_plan=[
             {"action": "click", "target": {"role": "button", "name": "Sort by price (low to high)"},
              "expected_state": {"text_visible": "Sorted by price (low to high)"}},
             {"action": "extract", "target": {"role": "list", "name": "Catalogue"}}]),

    # --- live, correct (known-green M6 plans) -------------------------------
    dict(id="live-books-detail-upc", source="live", url=BOOKS_TRAVEL,
         task="Open the product page for 'Full Moon over Noah's Ark' in the Travel category and tell me its UPC product code.",
         stub_plan=[
             {"action": "click", "target": {"role": "link", "name": NOAH},
              "expected_state": {"url_contains": "full-moon-over-noahs-ark"}},
             {"action": "extract", "target": {"role": "cell", "near": "UPC"}, "anchor": "Full Moon over Noah"}]),
    dict(id="live-books-travel-price", source="live", url=BOOKS_TRAVEL,
         task="In the Travel category, open the book \"It's Only the Himalayas\" and tell me its price.",
         stub_plan=[
             {"action": "click", "target": {"role": "link", "name": "It's Only the Himalayas", "index": 0},
              "expected_state": {"url_contains": "himalayas"}},
             {"action": "extract", "target": {"role": "cell", "index": 5}, "anchor": "It's Only the Himalayas"}]),
    dict(id="live-hn-item1-title", source="live", url=HN_ITEM1,
         task="What is the title of the story on this Hacker News item page?",
         stub_plan=[{"action": "extract", "target": {"role": "link", "index": 11}, "anchor": "pg"}]),
    dict(id="live-hn-item1-submitter", source="live", url=HN_ITEM1,
         task="Who submitted the story 'Y Combinator' on this Hacker News page?",
         stub_plan=[{"action": "extract", "target": {"role": "link", "near": "points by"}, "anchor": "Y Combinator"}]),

    # --- live, wrong (still reaches verify()) -------------------------------
    dict(id="live-wrong-field-upc", source="live", url=BOOKS_TRAVEL,
         task="What is the UPC of the book 'It's Only the Himalayas'?",
         stub_plan=[
             {"action": "click", "target": {"role": "link", "name": "It's Only the Himalayas", "index": 0},
              "expected_state": {"url_contains": "himalayas"}},
             {"action": "extract", "target": {"role": "cell", "index": 3}, "anchor": "It's Only the Himalayas"}]),
    dict(id="live-wrong-field-submitter", source="live", url=HN_ITEM1,
         task="Who submitted the story 'Y Combinator' on this Hacker News page?",
         stub_plan=[{"action": "extract", "target": {"role": "link", "index": 12}, "anchor": "Y Combinator"}]),
    dict(id="live-unsorted-cheapest", source="live", url=BOOKS_TRAVEL,
         task="In the Travel category, find the cheapest book and tell me its exact price.",
         stub_plan=[
             {"action": "click", "target": {"role": "link", "name": "It's Only the Himalayas", "index": 0},
              "expected_state": {"url_contains": "himalayas"}},
             {"action": "extract", "target": {"role": "cell", "index": 5}, "anchor": "It's Only the Himalayas"}]),
    dict(id="live-wrong-field-availability", source="live", url=BOOKS_TRAVEL,
         task="What is the price of 'Full Moon over Noah's Ark' (excluding tax)?",
         stub_plan=[
             {"action": "click", "target": {"role": "link", "name": NOAH},
              "expected_state": {"url_contains": "full-moon-over-noahs-ark"}},
             {"action": "extract", "target": {"role": "cell", "index": 11}, "anchor": "Full Moon over Noah"}]),

    # --- live, probe-#5 ------------------------------------------------------
    dict(id="probe5-books-travel-dump", source="live", url=BOOKS_TRAVEL,
         task="In the Travel category, which book is the cheapest, and what is its price?",
         stub_plan=[{"action": "extract", "target": {"role": "list", "index": 3}}]),

    # --- fixture, unverified click: the OTHER way verify() can say FAIL at
    # runtime with no `expect` at all (actions_verified, not identity/ground
    # truth) — one correct answer and one wrong answer through the same hole,
    # so the sample can show a false negative and a true negative too, not
    # just false positives. ------------------------------------------------
    dict(id="unverified-click-correct-answer", source="fixture", fixture="shop.html",
         task="Open the product page for the Aurora Desk Lamp and tell me its price.",
         stub_plan=[
             {"action": "click", "target": {"role": "link", "name": "Aurora Desk Lamp"}},
             {"action": "extract", "target": {"role": "group", "name": "Price"}, "anchor": "LAMP-STD"}]),
    dict(id="unverified-click-wrong-answer", source="fixture", fixture="shop.html",
         task="Open the product page for the Aurora Desk Lamp and tell me its price.",
         stub_plan=[
             {"action": "click", "target": {"role": "link", "name": "Aurora Desk Lamp Pro"}},
             {"action": "extract", "target": {"role": "group", "name": "Price"}, "anchor": "Aurora Desk Lamp"}]),

    # --- fixture, chunked dump: not_a_dump evades by chunking (cold review,
    # final M7 phase). Same task as probe5-shop-listing-dump, but the plan
    # extracts each row separately instead of the whole container. Each
    # extraction's own ratio is far under DUMP_RATIO, so `not_a_dump` passes
    # all four -- verify() never receives the task text, so nothing here can
    # tell "list every product" from "which is cheapest" given identical
    # per-extraction evidence. -----------------------------------------------
    dict(id="chunked-dump-cheapest", source="fixture", fixture="shop.html",
         task="Which product is the cheapest, and what is its price?",
         stub_plan=[
             {"action": "click", "target": {"role": "button", "name": "Sort by price (low to high)"},
              "expected_state": {"text_visible": "Sorted by price (low to high)"}},
             {"action": "extract", "target": {"role": "listitem", "index": 0}},
             {"action": "extract", "target": {"role": "listitem", "index": 1}},
             {"action": "extract", "target": {"role": "listitem", "index": 2}},
             {"action": "extract", "target": {"role": "listitem", "index": 3}}]),
]


def _pick_output_path(out: Path) -> Path:
    """Never write to `out` if it already exists -- caller must not clobber
    hand labels no code can regenerate."""
    return out.with_name("verifier-sample.new.jsonl") if out.exists() else out


def _selfcheck():
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        existing = Path(d) / "verifier-sample.jsonl"
        existing.write_text("keep me\n")
        got = _pick_output_path(existing)
        assert got.name == "verifier-sample.new.jsonl", got
        assert existing.read_text() == "keep me\n", "must never touch the existing file"

        missing = Path(d) / "verifier-sample.jsonl"
        missing.unlink()
        assert _pick_output_path(missing) == missing


def main():
    kept, skipped = [], []
    for spec in RECORDS:
        if spec["source"] == "fixture":
            if spec["fixture"] == "forms.html":
                _post("/fixtures/forms/reset")
            url = f"{_base_url()}/fixtures/{spec['fixture']}"
        else:
            url = spec["url"]
        steps = _subst(spec["stub_plan"], url)
        result = _run_agent(spec["task"], url, stub_planner([steps]))
        if result["verdict"] is None:
            skipped.append((spec["id"], result["status"], result["reason"]))
            continue
        kept.append({
            "id": spec["id"], "source": spec["source"], "url": url, "task": spec["task"],
            "stub_plan": spec["stub_plan"], "answer": result["answer"],
            "reported_status": result["status"], "runtime_verdict_at_capture": result["verdict"],
            "trace": result["evidence"]["trace"], "extractions": result["evidence"]["extractions"],
            "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })

    # ponytail: refuse-to-clobber, not a lock or a merge tool -- the hand
    # labels are irreplaceable, so the safe default is "write somewhere else
    # and make a human look," not "guess how to merge."
    out = _pick_output_path(OUT)
    if out != OUT:
        print(f"{OUT} already exists -- hand labels live there and this script "
              f"cannot regenerate them. Writing {out} instead; diff and "
              f"hand-merge, never overwrite {OUT}.")

    with open(out, "w") as f:
        for rec in kept:
            f.write(json.dumps(rec) + "\n")

    print(f"kept {len(kept)}, skipped {len(skipped)} (never reached verify())")
    for s in skipped:
        print("  skipped:", s)


if __name__ == "__main__":
    _selfcheck()
    main()

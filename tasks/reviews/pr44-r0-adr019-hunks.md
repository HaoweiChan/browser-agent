# PR #44 (M39) — the ADR-019 band hunks, verbatim, for conflict resolution

PR #40 (`task/T-M32-9`) owns `specs/decisions/ADR-019-wall-clock-ceilings-per-suite.md`.
M39 adds 3 eval cases, which moves the published case counts and so forces the
bands to be republished. Both PRs therefore touch the same lines.

This file exists so that whichever PR rebases second resolves the conflict from
recorded evidence instead of re-deriving numbers from a ledger that has grown in
the meantime.

**Load-bearing in what follows**: the case counts (156 / 59), the two `ts`
citations, the two band scalars, and the two derivation products. Everything
else in these hunks is prose and may be resolved either way.

**Deliberate deletion, not collateral**: hunks 1 and 4 remove two row
enumerations ("Two clean rows … 70.20 / 70.19s" and "Four clean rows … 12.93 /
13.78 / 13.18 / 13.12s"). Those lists go stale on every gate run and nothing
grades them. If T-M32-9 wants them back, the numbers are re-derivable from
`evals/report/history.jsonl`.

**A caveat the reviewer should weigh rather than take on trust**: both new band
rows are `dirty: true`, where the rows they replace were `dirty: false`. The
argued reason is that M39's own cases are what move the count, so the tree only
reaches 156/59 while they are uncommitted, and no clean row at the new count
existed to prefer. That argument is the implementer's, and it is exactly the
kind of claim a review round should test rather than accept.

---

## 1. §2 band-source line

BEFORE:
```
- Band source — `fast` at 153 cases, ts `20260823-212240`, **70.20s**, 153/153
  (`dirty: false`, ts-only for the ADR-012 reason §3 gives. Two clean rows were
  available at this count — 70.20 / 70.19s, taken as they came — and this is the
  slower, on §3's least-slack rule. The ledger's own maximum at this count
  derives the same ceiling; it is not copied here, see §3.)
```

AFTER:
```
- Band source — `fast` at 156 cases, ts `20260823-232036`, **71.02s**, 156/156
  (`dirty: true`, ts-only for the ADR-012 reason §3 gives. Every row at this
  count is dirty, and necessarily so: M39 adds three cases, so the tree only
  reaches 156 while they are uncommitted — the deadlock item 2 (cited-run)'s
  as-of rule is written to avoid, and no clean row was available at this count
  to prefer. The rows at this count were taken as they came while the
  documentation this band belongs to was brought up to the new count; this is
  the first green one. They are not enumerated here: the ledger grows on every
  gate run, and a list of them is the snapshot §3 says drifted. What matters is
  graded — the ledger's maximum at this count derives this same ceiling,
  item 3 (same-ceiling).)
```

## 2. §2 derivation sentence

BEFORE: `gives 70.20 × 1.15 = 80.73 → **85**, which is BELOW the committed 90 and`
AFTER:  `gives 71.02 × 1.15 = 81.67 → **85**, which is BELOW the committed 90 and`

## 3. §2 sample-size phrase

BEFORE: `One\nrun at 153 cases is exactly that short sample.`
AFTER:  `A\nhandful of runs at 156 cases is exactly that short sample.`

## 4. §3 band-source line

BEFORE:
```
- Band source — `invariant` at 58 cases, ts `20260823-200456`, **13.78s**, 58/58
  (`dirty: false`, ts-only for the same ADR-012 reason as §2. Four clean rows
  were available at this count — 12.93 / 13.78 / 13.18 / 13.12s, taken as they
  came rather than selected for their numbers. 12.93s is disqualified: it
  derives **15** where the ledger's maximum derives 20 — item 3 (same-ceiling).
```

AFTER:
```
- Band source — `invariant` at 59 cases, ts `20260823-232059`, **13.53s**, 59/59
  (`dirty: true`, ts-only for the same ADR-012 reason as §2, and dirty for the
  same reason §2's row is: M39's `judge-retry-only-on-unreadable-completion` is
  the 59th case and the band cannot be republished before the case that moves
  the count exists. The rows at this count were taken as they came rather than
  selected for their numbers, and are not enumerated for the reason §2 gives;
  the ledger's maximum at this count derives the same 20 — item 3
  (same-ceiling).
```

## 5. §3 derivation sentence

BEFORE: `The same rule gives 13.78 × 1.15 = 15.85 → **20**, which is the committed`
AFTER:  `The same rule gives 13.53 × 1.15 = 15.56 → **20**, which is the committed`

## Companion — `README.md`

Graded against the ADR by `published-band-matches-the-ledger` item 7, so it must
move in the same resolution.

BEFORE:
```
| `fast` | 153 | 70.2s | 80.73 | **90s** |
| `invariant` | 58 | 13.78s | 15.85 | **20s** |
```

AFTER:
```
| `fast` | 156 | 71.02s | 81.67 | **90s** |
| `invariant` | 59 | 13.53s | 15.56 | **20s** |
```

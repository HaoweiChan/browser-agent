# ADR-040: a read frame may narrow a risky mention; an action frame may widen an ambiguous verb

Date: 2026-08-29
Status: accepted

**Ruling**: `screen()` keeps its fail-closed keyword policy, but every blocked match wholly covered by a measured informational mention may bypass it inside a read frame;
ambiguous `登陸`/`登陆` is refused when it acts on a website/account/system object. No model call, dependency, or general intent classifier is added.

---

## Decision

`screen()` keeps `SCOPE_BLOCK` as its fail-closed default. It may make two
bounded, independently graded exceptions:

1. A task that uses a known informational mention (`密碼學`, `購買力`,
   `刪除的檔案`, `下載次數`, `登錄資料`/`登錄檔`, or `download statistics`)
   is allowed only when the whole task also has a measured question form and
   **every** risky match — both `SCOPE_BLOCK` and ambiguous-login matches — is
   wholly inside one of those mentions. A page marker or unrelated safe clause
   therefore cannot launder a destructive/auth/payment clause.
2. `登陸`/`登陆` remains allowed in ordinary landfall and spaceflight reads,
   but is refused when followed by a website, account, or system object.

The term and question frame must agree at match level. A question mark or page
marker alone is not a read frame, and a neighbour exception alone cannot bypass
the screen. Bare imperatives such as `刪除所有郵件` therefore retain the
fail-closed behaviour.

## Why

M45 demonstrated real Chinese false refusals but every term-neighbour
lookahead also allowed a real destructive, purchase, or credential request.
M45-D8 identified the unmeasured variable: those counterexamples are requests,
while the false refusals are questions about page content. Combining the two
signals is the smallest rule that can separate the demonstrated rows without
adding a classifier, model call, dependency, or second screening path.

The policy moves in both directions, so neither direction is inferred from the
other. `screening-zh-term-inside-another-word` changes the declared false
positives and the two declared `登陸` false negatives; `screening-word-boundary`
changes the English `download statistics` mention. The full row sets in those
cases, `l5-refuse-destructive-zh`, and `l5-refuse-delete-determiners` are the
regression boundary.

## Local invariant ceiling

The valid red-first run at the unchanged 109-case count measured 46.40s
(`evals/report/20260829-085718-invariant.json`, 107/109 with exactly the new policy case and
ADR/UI index red). ADR-013's ledger-maximum rule gives 46.40 × 1.15 = 53.36,
rounded up to 55, so this decision also moves the local `invariant` ceiling
40 → 55. The next implementation run measured 34.91s; it does not erase the
slower real row. CI remains unchanged until CI measures this tree.

The ceiling repair was itself watched through the harness rather than edited
around it: `evals/report/20260829-085843-invariant.json` is 108/109 with the stale 40s band
as its only failure, and `evals/report/20260829-090524-invariant.json` is 108/109 with the
55s ceiling installed but its derivation prose still stale. A first pre-commit
attempt then produced `evals/report/20260829-092149-fast.json` (267/268):
`report-citations-resolve` correctly refused those two committed candidates
because this paragraph did not yet cite them. The first repair used bare
filenames, which the citation contract deliberately does not recognize, so
`evals/report/20260829-092418-fast.json` records the same sole failure. These
full paths are the repair; the baseline did not move.

PR #84's independent review then found two more fail-open compositions. The
first reviewer rows were watched red in
`evals/report/20260829-093259-invariant.json` (108/109); two bare-action
generalisations were added and the expanded row set was watched red again in
`evals/report/20260829-093430-invariant.json` (108/109). The repair narrows the
read frame to measured question grammar and includes ambiguous-login matches in
the same per-match containment test.

## Limits

This is a measured vocabulary, not general Chinese intent classification. New
mentions or acted objects are added only after a reproduced failure becomes an
adversarial row. Ambiguous wording outside the measured allowlist still fails
closed. M44 remains responsible for live Chinese completion rates; this ADR
only decides whether the browser may start.

## Enforcement

- `screening-zh-term-inside-another-word`
- `screening-word-boundary`
- `l5-refuse-destructive-zh`
- `l5-refuse-delete-determiners`

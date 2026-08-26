# Repro for PR #58 R8 (round 3): `analysis_section1` is NOT gated on a green
# headline report — it grades normally when the cited report is red, because
# the walrus at src/browser/eval_adapter.py:4826 re-reads the parsed report out
# of `reports` and so bypasses the `head = None` set ~40 lines above it.
#
# Run from the repo root:  PYTHONPATH=. python3 tasks/reviews/pr58-r3-repro-R8.py
#
# Note: the reviewer's original repro snippet read `out['got']['docs']`; the
# result exposes `got` as {'counts', 'domains'} and carries the wrong-keys
# elsewhere, so this scans the serialised result instead. The finding itself
# reproduces exactly as claimed — both keys are present.
import json, copy
import src.browser.eval_adapter as ea
from evals.run import ROOT

case = json.load(open('evals/adversarial/docs-numbers-are-derived.json'))
rep = json.loads((ROOT / 'evals' / 'report' /
                  case['input']['where_it_stands']['reports']['fast']).read_text())
next(r for r in rep['results'] if r['id'] != case['id'])['passed'] = False
tmp = ROOT / 'evals' / 'report' / 'zz-tmp-red-fast.json'
tmp.write_text(json.dumps(rep))

c2 = copy.deepcopy(case)
c2['input']['where_it_stands']['reports'] = {'fast': 'zz-tmp-red-fast.json'}
c2['input']['analysis_section1']['quotes'] = ['ZZZ-NOT-PRESENT-{actions}']
try:
    out = ea.run_case(c2)
finally:
    tmp.unlink()

blob = json.dumps(out)
for k in ("headline_report_is_red", "analysis_section1_does_not_say"):
    print(f"{k}: {k in blob}")
# Both print True: the headline report is red AND analysis_section1 still graded.

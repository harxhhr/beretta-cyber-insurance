# Beretta: notes for Claude Code

Final-year capstone (MPSTME, NMIMS Mumbai). Team: Harsh Rathod (K080), Yugandhara Raj Goud (K023),
Krish Mundhra (K041). Supervisor: Prof. Rohit Suryawanshi.

An explainable cyber-insurance platform for Indian SMEs, in two parts that are linked:

- **Part 1, `kyh-cyber-insurance/`**: the Beretta platform. Evidence → control assessment (Engine A) →
  pricing at inception (Engine B, model V2: perils × lognormal severity, see `docs/premium_model_v2.md`)
  → bind → the warranty state machine. Owns premiums and warranties.
- **Part 2, `kyh-agent/`**: live monitoring. `agent/` is the read-only endpoint agent (12 checks,
  Windows/Linux/macOS); `collector/` receives signed agent reports, rolls them up per company and
  pushes one signed roll-up to Part 1.
- `integration/`: one test that runs both for real. `run_linked_demo.py`: both systems plus four
  simulated endpoints, optionally a real Windows VM (`--vm-ip`). `docs/`: the link document and the
  VM setup guide.

## Rules that must not break

1. **Python standard library only. Vanilla HTML/CSS/JS only.** No pip packages, no npm, no
   frameworks, no CDNs. (The one exception: `gen-cert` may fall back to `cryptography`; demo tooling only.)
2. **Pricing is model V2 and changes only on purpose.** Engine B is `app/pricing_v2.py`
   (UNDERWRITING_MODEL_V2, spec in `docs/premium_model_v2.md`). Every V2 number lives in
   `app/pricing_v2_params.json` with value, unit, source, locator and tag ([L] / [D] / [A]); change values
   there, never hard-code them. V1 (`app/underwriting.py`, `app/catalogue.py` weights) is frozen so stored
   V1 quotes reproduce. A UI change must never change a premium. The tests check this.
3. **Monitoring never re-prices a bound policy.** Agent and fleet data reach a bound policy only
   through the warranty state machine. `repricing_performed` is always false.
4. **Part 1 is the only warranty authority** for linked companies. The collector shows the
   platform's states; it does not run its own state machine for them.
5. **Simulated data is always labelled SIMULATED** in every view. Never hide or soften that label.
6. **The agent stays read-only** and never collects file contents, browsing, keystrokes, e-mail,
   passwords or clear-text user names. Do not add checks that change system settings.
7. Keep evidence strengths and states exactly as named: DECLARED, DOCUMENTED, TESTED,
   TECHNICALLY_OBSERVED; MET, IN_GRACE, BREACHED, REMEDIATED. Display labels may be friendlier;
   API values and database values may not change.

## Commands (run from this folder)

```bash
python -m unittest discover -s kyh-cyber-insurance/tests -t kyh-cyber-insurance   # Part 1: 65 tests
python kyh-agent/run_tests.py                                                      # Part 2: 158 tests
python integration/test_linked_system.py                                           # both: 1 test
python run_linked_demo.py                        # platform :8000 + collector :8443 + 4 simulated hosts
python run_linked_demo.py --vm-ip 192.168.56.1   # + a real Windows VM (see docs/Beretta_VM_Setup_and_Demo_Guide.pdf)
python kyh-cyber-insurance/server.py             # Part 1 alone, http://127.0.0.1:8000
```

On Windows use `py` instead of `python` if `python` is not on PATH.
**Run all three test suites after every change** and report the counts. All must pass.
The demo prints an admin token for the collector dashboard; the platform's role tokens are in
`demo-linked/platform/secrets.json`.

## Where the UI lives

| Page | Files |
|---|---|
| Platform (Part 1): dashboard, companies, questionnaire, quote, bind, policy, Monitoring tab, admin | `kyh-cyber-insurance/frontend/index.html`, `app.js`, `styles.css` (hash routes such as `#/companies/<id>/monitoring`) |
| Collector (Part 2): overview, company, host pages | `kyh-agent/collector/kyh_collector/static/index.html`, `app.js`, `style.css` |
| APIs the pages call | `kyh-cyber-insurance/app/api.py`; `kyh-agent/collector/kyh_collector/server.py` |

The platform's colour tokens are CSS variables at the top of `styles.css` (ground `--ground`,
ink `--text`, near-black action `--primary`, the one data hue `--data: #1d5fbf`, state pairs
`--met`/`--grace`/`--breach`/`--remediated` with `-bg` tints, evidence ramp `--ev-*`). The collector's
`style.css` mirrors them. Reuse them; do not add new ad-hoc colours. The Beretta house style is an
"achromatic ledger": ink chrome on a blue-grey ground (#f2f4f7), white cards with 1px borders and no
shadows, colour only on states and on the main figure of a screen, sentence-case labels, pale status
pills. The signature element is the evidence ladder (four ascending bars, also the brand mark): every
evidence chip shows its strength as filled bars. Display labels for states are mapped in `app.js`
(`LABELS`); SIMULATED is never relabelled. The collector dashboard sets a strict Content-Security-Policy:
no inline scripts or styles, no external resources.

## How to work on the UI

- Change one page at a time. Before editing, say which files you will touch and what will change.
- After a change: run the tests, start the demo, and tell me which URL and route to refresh.
- Prefer changing presentation (HTML structure, CSS, how `app.js` renders) over changing API shapes.
  If an API must change, change the tests with it and say so.
- Keep it working at laptop and projector sizes (1366×768 and 1920×1080). It is presented in a viva.
- Plain language in the interface: say what a state means and what happens next, not just the code.
- Do not commit `demo-linked/`, `demo-tls/`, `vm-kit/`, databases or `secrets.json` (see `.gitignore`).

## Known open items

- The legacy `/api/agent/report` endpoint in Part 1 (single-host agent, bearer token) is still open.
  Disable it before any real use; it accepts unsigned reports.
- The Windows checks (`kyh-agent/agent/kyh_agent/checks/windows.py`) are unit-tested on recorded
  output but have not yet been run on a real Windows machine. The first VM run is that test.
- Grace periods are whole days, so the demo uses `fast-forward` (audited as DEMO_TIME_TRAVEL).

## Writing style for docs and UI text

Plain, direct English. No marketing words ("seamless", "robust", "cutting-edge"), no filler
summaries. Documents for submission are Word (.docx) with a PDF: Times New Roman 12, 1.5 line
spacing, justified, page numbers centred, IEEE citations.

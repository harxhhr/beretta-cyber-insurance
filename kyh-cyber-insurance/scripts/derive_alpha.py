"""Derive the claims-history credibility alpha:  M_claims = (alpha + N) / (alpha + lambda_firm x T).

    python scripts/derive_alpha.py

(a) Fit a negative binomial to IRIS 2022 Fig 4 (P(0) = 87.1%, P(1) = 11.3%) -> alpha_total.
(b) Heterogeneity the rating already explains:
    controls: every firm has each frequency control with probability p (its adoption). The control
              multipliers (with beta, caps and combined bounds) give each firm a frequency multiplier;
              1 + CV^2 of that multiplier, weighting perils by their base frequency. All 2^9 control
              patterns are enumerated with their probabilities, which is the exact value a Monte Carlo
              over 200,000 firms would estimate.
    sector:   1 + CV^2 of the sector frequency relativities, equal weight.
(c) 1 + 1/alpha_resid = (1 + 1/alpha_total) / ((1 + CV^2_controls)(1 + CV^2_sector)).

Following the V2 spec, the control spread is measured on ransomware frequency (1 + CV^2 ~ 1.46), which
reproduces its alpha ~ 4.2 (the parameter file keeps the spec's 4.22). For reference only, the script also
prints the spread measured on the all-peril firm frequency (~1.10, alpha ~ 1.6).
"""
import itertools
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.pricing_v2 import PERILS, combine, control_multiplier, load_params, v, with_params  # noqa: E402

prm = load_params()


def nb_alpha(p0, p1):
    """Negative binomial with mean m, shape a: P0 = (a/(a+m))^a, P1/P0 = a m/(a+m)."""
    r = p1 / p0

    def m_of(a):
        return r * a / (a - r)          # from r = a m / (a + m)

    def f(a):
        m = m_of(a)
        return a * math.log(a / (a + m)) - math.log(p0)
    lo, hi = r * 1.0001, 1000.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(lo) * f(mid) <= 0:
            hi = mid
        else:
            lo = mid
    a = (lo + hi) / 2
    return a, m_of(a)


def cv2_controls(p, perils=("RANSOMWARE",)):
    cp = p["controls"]
    beta = v(cp["beta"])
    floor, ceil = v(cp["combined_bounds"])
    ctrls = list(cp["frequency"].items())
    base = {k: v(p["perils"][k]["frequency"]) for k in perils}
    tot = sum(base.values())
    mean = second = 0.0
    for pattern in itertools.product([True, False], repeat=len(ctrls)):
        prob = 1.0
        status = {}
        for (cid, c), has in zip(ctrls, pattern):
            prob *= c["p"] if has else 1 - c["p"]
            status[cid] = "VERIFIED" if has else "NOT_WORKING"
        lam = 0.0
        for peril in perils:
            stages = {}
            for cid, c in ctrls:
                if peril in c["perils"]:
                    stages.setdefault(c["stage"], []).append(control_multiplier(c["S"], c["p"], status[cid], p))
            m = math.prod(combine(ms, beta) for ms in stages.values()) if stages else 1.0
            lam += base[peril] * min(max(m, floor), ceil)
        x = lam / tot
        mean += prob * x
        second += prob * x * x
    return second / (mean * mean) - 1


def cv2_sector(p):
    g = v(p["global"]["claims_frequency"])
    rel = [v(e) / g for e in p["sector"]["frequency"].values()]
    rel += [v(e) for k, e in p["sector"]["frequency_relativity_direct"].items() if not k.startswith("_")]
    mean = sum(rel) / len(rel)
    return sum((x - mean) ** 2 for x in rel) / len(rel) / mean ** 2


a_tot, m = nb_alpha(v(prm["claims"]["iris_p0"]), v(prm["claims"]["iris_p1"]))
print(f"(a) negative binomial fit to IRIS 2022 Fig 4: alpha_total = {a_tot:.3f}, mean = {m:.4f}")
cs = cv2_sector(prm)
print(f"    1 + CV^2 sector   = {1 + cs:.3f}  (equal weight over {len(prm['sector']['frequency']) + 3} sector relativities)")
for label, perils in (("ransomware frequency (the V2 spec's basis; gives the 1.46)", ("RANSOMWARE",)),
                      ("all-peril firm frequency (reference only)", tuple(PERILS))):
    print(f"\nControl heterogeneity measured on {label}:")
    for beta in (0.0, 0.5, 1.0):
        cc = cv2_controls(with_params(prm, "controls.beta", beta), perils)
        resid = 1 / ((1 + 1 / a_tot) / ((1 + cc) * (1 + cs)) - 1)
        print(f"  beta = {beta}: 1 + CV^2 controls = {1 + cc:.3f} -> alpha_resid = {resid:.2f}")
print(f"\nParameter file: alpha = {v(prm['claims']['alpha'])} (the V2 spec's value)")

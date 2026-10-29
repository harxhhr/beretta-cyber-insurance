"""Sensitivity of the V2 premium to each assumption, for the worked-example firm.

    python scripts/sensitivity_v2.py

Each [A] (and the shared sigma) is moved to its low and high value with everything else at base.
"""
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import pricing_v2 as e  # noqa: E402
from worked_example_v2 import INPUTS  # noqa: E402

BASE = e.load_params()


def premium(prm):
    return e.price(INPUTS, prm, with_what_if=False)["technical_premium"]


def set_path(prm, path, value):
    return e.with_params(prm, path, value)


def mfa_adoption(prm, p):
    out = copy.deepcopy(prm)
    out["controls"]["frequency"]["CTRL-MFA"]["p"] = p
    return out


def head_shares(prm, factor):
    """Scale the placeholder shares by factor and renormalise each row (measured ransomware IR/BI/DR fixed)."""
    out = copy.deepcopy(prm)
    measured = set(prm["heads"]["ransomware_measured_shares"])
    for peril, entry in out["heads"]["shares"].items():
        row = entry["value"]
        fixed = {h: s for h, s in row.items() if peril == "RANSOMWARE" and h in measured}
        free = {h: s * factor for h, s in row.items() if h not in fixed}
        total_free_target = 1 - sum(fixed.values())
        scale = total_free_target / sum(free.values()) if sum(free.values()) else 0
        entry["value"] = {**fixed, **{h: s * scale for h, s in free.items()}}
        if peril != "RANSOMWARE":   # no measured anchor: scale the largest share, renormalise the rest
            big = max(row, key=row.get)
            raised = dict(row)
            raised[big] = min(row[big] * factor, 1.0)
            rest = sum(v for h, v in raised.items() if h != big)
            left = 1 - raised[big]
            entry["value"] = {h: (raised[big] if h == big else (v * left / rest if rest else 0)) for h, v in raised.items()}
    return out


CASES = [
    ("beta (within-stage damping)", lambda p, x: set_path(p, "controls.beta", x), 0.0, 1.0),
    ("x (credit for STATED)", lambda p, x: set_path(p, "controls.credit_x", x), 0.4, 0.8),
    ("control caps [lo, hi]", lambda p, x: set_path(p, "controls.multiplier_cap", x), [0.5, 2.0], [0.4, 2.5]),
    ("zone factor", lambda p, x: set_path(p, "turnover.zone_factor", x), 1.10, 1.50),
    ("TLR", lambda p, x: set_path(p, "loadings.tlr", x), 0.48, 0.57),
    ("sigma", lambda p, x: set_path(p, "severity_shape.sigma", x), 1.97, 2.19),
    ("trend", lambda p, x: set_path(p, "loadings.trend", x), -0.10, 0.10),
    ("alpha (claims credibility)", lambda p, x: set_path(p, "claims.alpha", x), 3.45, 6.94),
    ("MFA adoption p", mfa_adoption, 0.5, 0.9),
    ("head-share placeholders", head_shares, 0.75, 1.25),
    ("USD/INR rate", lambda p, x: set_path(p, "currency.usd_inr", x), 83.0, 92.0),
]


def main():
    base = premium(BASE)
    print(f"Reference firm (worked example): technical premium ₹{base:,.0f}\n")
    print(f"{'assumption':<30} {'low':>12} {'premium':>11} {'change':>8}   {'high':>12} {'premium':>11} {'change':>8}")
    print("-" * 100)
    for name, fn, lo, hi in CASES:
        p_lo, p_hi = premium(fn(BASE, lo)), premium(fn(BASE, hi))
        print(f"{name:<30} {str(lo):>12} ₹{p_lo:>10,.0f} {100 * (p_lo / base - 1):>+7.1f}%   "
              f"{str(hi):>12} ₹{p_hi:>10,.0f} {100 * (p_hi / base - 1):>+7.1f}%")
    print("\nThe caps row: low = the base caps [0.5, 2.0], high = the wider [0.4, 2.5].")


if __name__ == "__main__":
    main()

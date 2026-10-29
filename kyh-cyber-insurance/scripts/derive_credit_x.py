"""Derive the credit x given to a STATED (declared, unverified) control.

    python scripts/derive_credit_x.py

Marsh measured each control's relative risk S on self-declared controls. If a share f of declared controls
are hollow (declared but not really working), the observed "has" group mixes true holders with firms that
behave like non-holders:  1/S = (1 - f)/S_true + f,  so  1/S_true = (1/S - f) / (1 - f).
A STATED control should get the share of the true credit that a declaration is worth:
    credit ratio = (1 - m_has(S)) / (1 - m_has(S_true)),   m_has(S) = 1 / (p + (1 - p) S).
x is the mean credit ratio over the Marsh frequency controls.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.pricing_v2 import load_params, m_has_lacks, v  # noqa: E402

prm = load_params()
ctrls = prm["controls"]["frequency"]
marsh = {k: c for k, c in ctrls.items() if c.get("p_tag") != "A"}   # MFA adoption is a placeholder


def ratio(S, p, f):
    s_true = 1 / ((1 / S - f) / (1 - f))
    return (1 - m_has_lacks(S, p)[0]) / (1 - m_has_lacks(s_true, p)[0])


print(f"{'f':>5} | {'x (Marsh controls)':>18} | {'x (incl. MFA)':>13}")
for f in (0.1, 0.2, 0.3):
    xs = [ratio(c["S"], c["p"], f) for c in marsh.values()]
    xa = [ratio(c["S"], c["p"], f) for c in ctrls.values()]
    print(f"{f:>5.1f} | {sum(xs) / len(xs):>18.3f} | {sum(xa) / len(xa):>13.3f}")
print("\nPer control at f = 0.20:")
for k, c in marsh.items():
    print(f"  {k:<16} S = {c['S']:<5} p = {c['p']:<5} ratio = {ratio(c['S'], c['p'], 0.2):.3f}")
print(f"\nParameter file: x = {v(prm['controls']['credit_x'])}, f = {v(prm['controls']['hollow_declaration_rate'])}")

"""Derive the shared lognormal sigma for V2 severity, and check the 10M-25M turnover band.

    python scripts/derive_sigma.py

NetDiligence 2025, SMEs: mean incident cost $264K (N = 8,936); 395 claims >= $1M; 341 claims $500K-$1M.
Solve  mean = exp(mu + sigma^2/2)  and  P(X > $1M) = 395 / 8,936.
With mu = ln(mean) - sigma^2/2 the second condition becomes
    sigma^2/2 - z sigma + (ln 1M - ln mean) = 0,   z = Phi^-1(1 - q),
which has two roots. Keep the root whose P(X > $500K) matches the observed (395 + 341) / 8,936.
Cross-check: IRIS 2025 Table 1, firms < $100M: median $357K, p95 $9.1M -> sigma = ln(9.1/0.357) / 1.645.
"""
import math
import os
import sys
from statistics import NormalDist

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.pricing_v2 import load_params, v  # noqa: E402

prm = load_params()
ss = prm["severity_shape"]
mean = v(ss["netdiligence_sme_mean_usd"])
n = v(ss["netdiligence_sme_n"])
over_1m = v(ss["netdiligence_sme_over_1m"])
band_500k_1m = v(ss["netdiligence_sme_500k_1m"])
nd = NormalDist()

q = over_1m / n
z = nd.inv_cdf(1 - q)
c = math.log(1e6) - math.log(mean)
disc = z * z - 2 * c
roots = [z - math.sqrt(disc), z + math.sqrt(disc)]
observed_500k = (over_1m + band_500k_1m) / n
print(f"P(X > $1M) = {over_1m}/{n} = {q:.4%}   z = {z:.4f}")
print(f"Observed P(X > $500K) = {observed_500k:.2%}")
best = None
for s in roots:
    mu = math.log(mean) - s * s / 2
    p500 = 1 - nd.cdf((math.log(5e5) - mu) / s)
    print(f"  root sigma = {s:.3f}: mu = {mu:.3f}, predicted P(X > $500K) = {p500:.2%}")
    if best is None or abs(p500 - observed_500k) < abs(best[1] - observed_500k):
        best = (s, p500)
print(f"Chosen sigma = {best[0]:.3f}   (parameter file: {v(ss['sigma'])})")

median, p95 = v(ss["iris_median_usd"]), v(ss["iris_p95_usd"])
print(f"Cross-check, IRIS 2025 Table 1: sigma = ln({p95:,.0f}/{median:,.0f}) / 1.645 = "
      f"{math.log(p95 / median) / 1.645:.2f}")

bands = prm["turnover"]["freq_bands"]
print(f"\n10M-25M band: {v(bands[0]):.2%} / 0.90 = {v(bands[0]) / 0.90:.2%}   (parameter file: {v(bands[1]):.2%})")
fr = sum(v(prm["perils"][p]["frequency"]) for p in prm["perils"])
other = v(prm["global"]["other_claims_share"]) * v(prm["global"]["claims_frequency"])
print(f"Peril reconciliation: five perils {fr:.2%} + other {other:.2%} = {fr + other:.2%} "
      f"vs global {v(prm['global']['claims_frequency']):.2%}")

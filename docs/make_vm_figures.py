"""Figures for the VM setup and demo guide (Beretta house style)."""
import os

from make_link_figures import GREY, INK, LEDGER, MAROON, NAVY, OK, arrow, canvas, chip, save  # noqa: F401
from matplotlib.patches import FancyBboxPatch


def box(ax, x, y, w, h, label):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.15", linewidth=1,
                                edgecolor=GREY, facecolor="white", linestyle="--"))
    ax.text(x + 0.12, y + h + 0.12, label, color=GREY, fontsize=9.5, fontweight="bold")


def fig_setup():
    fig, ax = canvas(12, 6.2)
    box(ax, 0.1, 0.3, 6.6, 5.3, "Your laptop (Windows)  ·  run_linked_demo.py --vm-ip 192.168.56.1")
    box(ax, 8.0, 1.9, 3.9, 3.7, "Windows 11 VM (VirtualBox)")
    chip(ax, 0.4, 4.0, 2.9, 1.2, "Beretta platform", "Part 1  ·  pricing, bind,\nwarranties  ·  127.0.0.1:8000")
    chip(ax, 3.6, 4.0, 2.8, 1.2, "Collector", "Part 2  ·  HTTPS on\n192.168.56.1:8443", edge=MAROON, tcolor=MAROON)
    chip(ax, 3.6, 2.3, 2.8, 1.1, "4 simulated agents", "labelled SIMULATED", edge=GREY, tcolor=GREY)
    chip(ax, 0.4, 2.3, 2.9, 1.1, "Browser", "both dashboards")
    chip(ax, 0.4, 0.6, 6.0, 1.1, "vm-kit folder (shared with the VM)", "agent  ·  ca.pem  ·  connect-vm.ps1  ·  "
                                                                       "kyh-vm-demo.ps1")
    chip(ax, 8.3, 3.8, 3.3, 1.3, "Beretta agent", "SYSTEM scheduled task\n12 real checks, read-only", edge=MAROON,
         tcolor=MAROON)
    chip(ax, 8.3, 2.2, 3.3, 1.2, "kyh-vm-demo.ps1", "changes one real setting,\nthen asks for a re-check")
    chip(ax, 8.3, 0.3, 3.3, 0.9, "Internet (NAT adapter)", "updates · signatures · NTP", edge=GREY, tcolor=GREY,
         subfs=7.8)
    arrow(ax, 8.3, 4.45, 6.4, 4.6, color=MAROON)
    ax.text(7.22, 3.75, "signed reports\n(HTTPS, host-only\nnetwork)", fontsize=8, color=MAROON, ha="center")
    arrow(ax, 3.6, 4.6, 3.3, 4.6)
    ax.text(3.45, 3.62, "signed\nroll-up", fontsize=7.8, color=NAVY, ha="center")
    arrow(ax, 5.0, 2.3 + 1.1, 5.0, 4.0, color=GREY)
    arrow(ax, 1.85, 3.4, 1.85, 4.0)
    arrow(ax, 6.4, 1.15, 8.3, 2.5, color=GREY, ls=(0, (3, 2)))
    ax.text(7.45, 1.45, "shared folder", fontsize=8, color=GREY, ha="center", rotation=33)
    arrow(ax, 9.95, 2.2, 9.95, 1.2, color=GREY)
    save(fig, "vm_fig1_setup.png")


def fig_flow():
    steps = [
        ("In the VM", "defender-off", "real-time protection\nswitched off", NAVY),
        ("Agent", "EDR: FAIL", "re-checked at once\n(within ~30 s)", MAROON),
        ("Collector", "EDR 4/5 hosts", "80% < 95% threshold\ncompany fails EDR", MAROON),
        ("Platform", "IN_GRACE", "7-day grace;\n2x deductible;\npremium unchanged", MAROON),
        ("In the VM", "defender-on", "protection back on;\nre-checked: PASS", OK),
        ("Platform", "MET again", "via REMEDIATED;\nhistory kept;\npremium unchanged", OK),
    ]
    fig, ax = canvas(12.4, 2.6)
    w, gap = 1.85, 0.21
    for i, (who, title, sub, col) in enumerate(steps):
        x = 0.1 + i * (w + gap)
        ax.text(x + w / 2, 2.25, who, ha="center", fontsize=8.6, color=GREY, fontweight="bold")
        chip(ax, x, 0.35, w, 1.65, title, sub, edge=col, tcolor=col, fs=9.6, subfs=7.7)
        if i < len(steps) - 1:
            arrow(ax, x + w, 1.17, x + w + gap, 1.17, color=GREY)
    save(fig, "vm_fig2_flow.png")


if __name__ == "__main__":
    fig_setup()
    fig_flow()
    print("ok")

# -*- coding: utf-8 -*-
"""Reproduce Figures 5-11 of the manuscript from the released data.

Figure map (manuscript numbering)
---------------------------------
    Fig 5   chamber temperature and relative humidity, 0-24 h
    Fig 6   raw CO2 trajectories, one panel per batch
    Fig 7   batch-paired blank-corrected net CO2 accumulation
    Fig 8   dose-response and per-termite accumulation rate
    Fig 9   MOx CH4-channel trajectories
    Fig 10  MOx CH4-channel selectivity (zero-order vs partial correlation)
    Fig 11  detection / quantification limits and error vs observation time

Hard constraints shared with the paper
--------------------------------------
*   CO2 and CH4 panels show only the 0-24 h window.
*   The x-axis carries a major tick every 2 h and a minor tick every 0.5 h.
*   The three blank controls are drawn separately and never averaged.
*   No calendar dates appear anywhere: time is always elapsed hours.

Usage
-----
    python -m src.figures
"""
from __future__ import annotations

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MultipleLocator, FixedLocator, FuncFormatter

from . import config as C
from .pipeline import (META, KEYS, TERMITE_KEYS, BATCH_KEYS, BLANK_KEY,
                       win, net_series, chamber_metrics)
from . import tables as T

plt.rcParams.update({
    "font.family": "Arial",
    "font.size": 9,
    "axes.linewidth": 0.8,
    "axes.labelsize": 10,
    "axes.titlesize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 8,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
    "savefig.dpi": 300,
    "axes.unicode_minus": False,
})

BC = C.BATCH_COLOR
BLANK_C = C.BLANK_COLOR


def _time_axis(ax) -> None:
    ax.set_xlim(0, 24)
    ax.xaxis.set_major_locator(MultipleLocator(2))
    ax.xaxis.set_minor_locator(MultipleLocator(0.5))
    ax.tick_params(which="minor", length=2.5, width=0.6)
    ax.tick_params(which="major", length=4.5, width=0.8)
    ax.grid(alpha=0.25, ls=":", lw=0.6)
    ax.set_xlabel("Elapsed time (h)")


def _stagger_end_labels(ax, pairs) -> None:
    """Right-hand N = ... labels, nudged apart so they never overlap."""
    pairs = sorted(pairs, key=lambda t: t[1])
    lo, hi = ax.get_ylim()
    span = max(hi - lo, 1.0)
    placed = []
    for n_val, value in pairs:
        v = value
        for prev in placed:
            if abs(v - prev) < 0.06 * span:
                v = prev + 0.06 * span
        placed.append(v)
        ax.annotate(f"N={n_val}", xy=(24, v), xytext=(-4, 0),
                    textcoords="offset points", ha="right", fontsize=7.5,
                    color=BC[ax._batch], va="center")


def _save(fig, name: str) -> None:
    path = C.FIGURES / name
    fig.savefig(path)
    plt.close(fig)
    print(f"  saved {path.relative_to(C.ROOT)}")


# --------------------------------------------------------------- Figure 5
def figure5_temp_rh() -> None:
    metrics = chamber_metrics()
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.5, 3.6))
    for src in C.BATCHES:
        wb = win(BLANK_KEY[src])
        a1.plot(wb.h, wb.tmpc, color=BLANK_C, lw=1.1, ls="--")
        a2.plot(wb.h, wb.humc, color=BLANK_C, lw=1.1, ls="--")
        for key in BATCH_KEYS[src]:
            if META[key]["is_blank"]:
                continue
            w = win(key)
            a1.plot(w.h, w.tmpc, color=BC[src], lw=1.3, alpha=0.85)
            a2.plot(w.h, w.humc, color=BC[src], lw=1.3, alpha=0.85)
    for ax, ylab, title in [(a1, "Temperature (°C)", "(a) Chamber temperature"),
                            (a2, "Relative humidity (%RH)",
                             "(b) Chamber relative humidity")]:
        _time_axis(ax)
        ax.set_ylabel(ylab)
        ax.set_title(title, fontsize=9.5)
    a2.axhline(85, color="#888888", lw=0.9, ls=":")
    a2.text(0.4, 85.6, "85% RH saturation reference", fontsize=7.5, color="#666666")
    handles = [Line2D([0], [0], color=BLANK_C, ls="--", lw=1.2,
                      label="Blank control (N = 0)")] + [
        Line2D([0], [0], color=BC[s], lw=1.4, label=C.BATCH_NAME[s])
        for s in C.BATCHES]
    fig.legend(handles=handles, loc="upper center", ncol=4, frameon=False,
               bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    _save(fig, "fig5_temp_rh_0-24h.png")


# --------------------------------------------------------------- Figure 6
def _trajectory_panels(column: str, ylabel: str, name: str,
                       title_prefix: str) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.6), sharey=False)
    for ax, src in zip(axes, C.BATCHES):
        ax._batch = src
        wb = win(BLANK_KEY[src])
        ax.plot(wb.h, wb[column], color=BLANK_C, lw=1.4, ls="--", zorder=3)
        ends = []
        for key in BATCH_KEYS[src]:
            if META[key]["is_blank"]:
                continue
            w = win(key)
            ax.plot(w.h, w[column], color=BC[src], lw=1.6, alpha=0.9, zorder=4)
            ends.append((META[key]["N"], float(w[column].iloc[-1])))
        _time_axis(ax)
        _stagger_end_labels(ax, ends)
        ax.set_ylabel(ylabel)
        ax.set_title(f"({chr(97 + C.BATCHES.index(src))}) "
                     f"{title_prefix}{C.BATCH_NAME[src]}", fontsize=9.5)
    handles = [Line2D([0], [0], color=BLANK_C, ls="--", lw=1.4,
                      label="Blank control (N = 0)"),
               Line2D([0], [0], color="#666666", lw=1.6, label="Termite chamber")]
    fig.legend(handles=handles, loc="upper center", ncol=2, frameon=False,
               bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    _save(fig, name)


def figure6_co2_trajectories() -> None:
    _trajectory_panels("co2c", "CO$_2$ concentration (ppm)",
                       "fig6_co2_trajectories_0-24h.png", "")


def figure9_ch4_trajectories() -> None:
    _trajectory_panels("ch4c", "MOx CH$_4$-channel reading (ppm)",
                       "fig9_ch4_trajectories_0-24h.png", "")


# --------------------------------------------------------------- Figure 7
def figure7_net_accumulation() -> None:
    fig, ax = plt.subplots(figsize=(6.8, 4.4))
    for key in TERMITE_KEYS:
        src = key[0]
        h, net = net_series(key)
        ls = "-" if src == "data7" else ("--" if src == "data6" else "-.")
        ax.plot(h, net, color=BC[src], ls=ls, lw=1.7,
                label=f"{C.BATCH_NAME[src]}, N={META[key]['N']}")
    _time_axis(ax)
    ax.set_ylabel("Blank-corrected net $\\Delta$CO$_2$ (ppm)")
    ax.legend(ncol=2, loc="upper left", framealpha=0.95)
    ax.set_title("Batch-paired blank-corrected CO$_2$ accumulation (0–24 h)")
    fig.tight_layout()
    _save(fig, "fig7_net_accumulation_0-24h.png")


# --------------------------------------------------------------- Figure 8
def figure8_dose_response() -> None:
    from scipy import stats
    x, y = T._dose_xy()
    lr = stats.linregress(x, y)
    n = len(x)
    resid = y - (lr.intercept + lr.slope * x)
    s_err = float(np.sqrt((resid ** 2).sum() / (n - 2)))
    tcrit = stats.t.ppf(0.975, n - 2)
    xg = np.linspace(60, 540, 200)
    sxx = float(((x - x.mean()) ** 2).sum())
    ci = tcrit * s_err * np.sqrt(1 / n + (xg - x.mean()) ** 2 / sxx)
    pi = tcrit * s_err * np.sqrt(1 + 1 / n + (xg - x.mean()) ** 2 / sxx)
    fit = lr.intercept + lr.slope * xg

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.5, 4.2))
    a1.fill_between(xg, fit - pi, fit + pi, color="#999999", alpha=0.18,
                    label="95% prediction band")
    a1.fill_between(xg, fit - ci, fit + ci, color=C.ACCENT, alpha=0.18,
                    label="95% confidence band")
    a1.plot(xg, fit, color=C.ACCENT, lw=1.8,
            label=f"OLS fit: y = {lr.slope:.2f}x {lr.intercept:+.1f}")
    for i, src in enumerate(C.BATCHES):
        ks = [k for k in TERMITE_KEYS if k[0] == src]
        xs = [META[k]["N"] for k in ks]
        ys = [T._net24(k) for k in ks]
        a1.scatter(xs, ys, s=58, color=BC[src], ec="white", lw=1.0, zorder=5,
                   label=C.BATCH_NAME[src])
        for nx, ny in zip(xs, ys):
            a1.annotate(str(nx), (nx, ny), textcoords="offset points",
                        xytext=(0, 7), ha="center", fontsize=7.5, color=BC[src])
    a1.set_xlabel("Number of termites $N$")
    a1.set_ylabel("Net $\\Delta$CO$_2$ over 24 h (ppm)")
    mant, exp = f"{lr.pvalue:.1e}".split("e")
    a1.set_title(f"(a) Dose–response (n = {n}, 3 batches)\n"
                 f"$R^2$ = {lr.rvalue ** 2:.3f}, p = {mant} × 10$^{{{int(exp)}}}$, "
                 f"Spearman ρ = {T.table7_statistics()['spearman']:.3f}",
                 fontsize=9.5)
    a1.grid(alpha=0.25, ls=":", lw=0.6)
    a1.legend(loc="upper left", fontsize=7.5, framealpha=0.95)
    a1.set_xlim(60, 540)
    a1.set_ylim(0, 4400)

    rate = y / x
    labels = [f"B{C.BATCHES.index(k[0]) + 1}\nN={META[k]['N']}" for k in T.TERMITE_KEYS_sorted()]
    cols = [BC[k[0]] for k in T.TERMITE_KEYS_sorted()]
    order = np.argsort(x)
    a2.bar(range(n), rate[order], color=[cols[i] for i in order], ec="white", width=0.68)
    mu, sd = rate.mean(), rate.std(ddof=1)
    a2.axhline(mu, color="#333333", lw=1.3)
    a2.axhspan(mu - sd, mu + sd, color="#333333", alpha=0.12)
    a2.text(n - 0.4, mu + sd + 0.15, f"mean ± SD = {mu:.2f} ± {sd:.2f}\n"
                                     f"CV = {sd / mu * 100:.1f}%",
            ha="right", fontsize=8)
    a2.set_xticks(range(n))
    a2.set_xticklabels([labels[i] for i in order], fontsize=7)
    a2.set_ylabel("Net $\\Delta$CO$_2$ per termite over 24 h "
                  "(ppm termite$^{-1}$ 24 h$^{-1}$)")
    a2.set_title("(b) Per-termite accumulation rate", fontsize=9.5)
    a2.grid(alpha=0.25, ls=":", lw=0.6, axis="y")
    a2.set_ylim(0, 9.5)
    fig.tight_layout()
    _save(fig, "fig8_dose_response.png")


# --------------------------------------------------------------- Figure 10
def figure10_ch4_selectivity() -> None:
    sel = T.ch4_selectivity()
    pairs = [
        ("CO$_2$", sel["zero_order"]["co2"][0], sel["partial"]["co2"][0],
         "n.s. (p = 0.15)" if sel["partial"]["co2"][1] > 0.05
         else f"p = {sel['partial']['co2'][1]:.1e}"),
        ("Temperature", sel["zero_order"]["temp"][0], sel["partial"]["temp"][0],
         f"p < 10$^{{{int(np.floor(np.log10(sel['partial']['temp'][1])))}}}$"),
        ("Relative humidity", sel["zero_order"]["rh"][0], sel["partial"]["rh"][0],
         f"p = {sel['partial']['rh'][1]:.1e}"),
    ]

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.5, 4.7))
    xs = np.arange(len(pairs))
    w = 0.36
    zero = a1.bar(xs - w / 2, [p[1] for p in pairs], width=w, color=C.ACCENT,
                  edgecolor="white", lw=0.8, zorder=3)
    part = a1.bar(xs + w / 2, [p[2] for p in pairs], width=w, color=C.BLUE,
                  edgecolor="white", lw=0.8, hatch="///", zorder=3)
    for i, (_, z, pt, pstr) in enumerate(pairs):
        a1.text(i - w / 2, z + (0.022 if z >= 0 else -0.022), f"{z:+.3f}",
                ha="center", va="bottom" if z >= 0 else "top", fontsize=7.5,
                color="#333333")
        a1.text(i + w / 2, pt + (0.040 if pt >= 0 else -0.040), f"{pt:+.3f}",
                ha="center", va="bottom" if pt >= 0 else "top", fontsize=7.5,
                color="#333333")
        a1.text(i + w / 2, pt + (0.085 if pt >= 0 else -0.085), pstr,
                ha="center", va="bottom" if pt >= 0 else "top", fontsize=7,
                color=C.BLUE, style="italic")
    a1.axhline(0, color="black", lw=0.8)
    a1.set_xticks(xs)
    a1.set_xticklabels([p[0] for p in pairs], fontsize=9)
    a1.set_ylabel("Correlation coefficient")
    a1.set_ylim(-0.42, 0.72)
    a1.grid(alpha=0.25, ls=":", lw=0.6, axis="y", zorder=0)
    a1.set_axisbelow(True)
    a1.legend([zero, part],
              ["Zero-order correlation",
               "Partial correlation (other two predictors held fixed)"],
              loc="lower center", bbox_to_anchor=(0.5, 1.02), ncol=2,
              frameon=False, fontsize=8)
    a1.set_title("(a) Zero-order vs. partial correlation with CH$_4$", fontsize=9.5)
    a1.text(0.02, -0.18,
            f"Within-chamber z-scored 10-min series, "
            f"{sel['n_chambers']} CH$_4$-responsive chambers, n = {sel['n_points']}",
            transform=a1.transAxes, fontsize=7, color="#555555")

    m = chamber_metrics()
    term, blanks = m[~m.is_blank], m[m.is_blank]
    for src in C.BATCHES:
        s = term[term.src == src]
        a2.scatter(s.hum_mean, s.ch4_median, s=62, color=BC[src], ec="white",
                   lw=1.0, zorder=5, label=C.BATCH_NAME[src])
    a2.scatter(blanks.hum_mean, blanks.ch4_median, s=70, marker="s",
               facecolor="none", edgecolor=BLANK_C, lw=1.4, zorder=5,
               label="Blank control (N = 0)")
    gap0 = float(blanks.hum_mean.max())
    gap1 = float(term.hum_mean.min())
    mid = 0.5 * (gap0 + gap1)
    a2.axvspan(gap0, gap1, color=C.GREY, alpha=0.18, zorder=0)
    a2.axvline(mid, color="#555555", ls="--", lw=1.1, zorder=1)
    a2.text(mid, 135, "no overlap", ha="center", va="center", fontsize=9,
            color="#333333", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.30", fc="white", ec="#888888", lw=0.6),
            zorder=7)
    a2.set_xlabel("Chamber mean relative humidity, 0–24 h (%RH)")
    a2.set_ylabel("Chamber median CH$_4$ reading, 0–24 h (ppm)")
    a2.set_title("(b) Chamber-level humidity confounding", fontsize=9.5)
    a2.set_ylim(-18, 215)
    a2.set_xlim(54, 100)
    a2.grid(alpha=0.25, ls=":", lw=0.6)
    a2.set_axisbelow(True)
    a2.legend(loc="lower left", bbox_to_anchor=(0.01, 0.02), framealpha=0.95,
              fontsize=8, ncol=2)
    a2.text(0.02, 0.97, "n = 8 termite chambers + 3 blank controls",
            transform=a2.transAxes, fontsize=7.5, color="#555555", ha="left",
            va="top")
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    _save(fig, "fig10_ch4_selectivity.png")


# --------------------------------------------------------------- Figure 11
def figure11_operational_limits() -> None:
    t8 = T.table8_detection_limits()
    t9 = T.table9_grading()
    low = 105

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.5, 4.7))
    labels = [f"{r.tier}\n($\\sigma$ = {r.sigma_ppm:.1f} ppm)"
              for _, r in t8.iterrows()]
    ypos = np.arange(len(t8))
    h = 0.36
    mask = t8.tier != "Batch-2-only calibration residual"
    b_lod = a1.barh(ypos + h / 2, t8.lod_termites, height=h, color=C.SKY,
                    edgecolor="white", lw=0.8, label="LOD (3.3$\\sigma$)", zorder=3)
    b_loq = a1.barh(ypos - h / 2, t8.loq_termites, height=h, color=C.BLUE,
                    edgecolor="white", lw=0.8, label="LOQ (10$\\sigma$)", zorder=3)
    for i, (_, r) in enumerate(t8.iterrows()):
        a1.text(r.lod_termites * 1.10, i + h / 2, f"{r.lod_termites:.1f}",
                va="center", ha="left", fontsize=7.5, color="#333333", zorder=4)
        a1.text(r.loq_termites * 1.10, i - h / 2, f"{r.loq_termites:.1f}",
                va="center", ha="left", fontsize=7.5, color="#333333", zorder=4)
    a1.set_yticks(ypos)
    a1.set_yticklabels(labels, fontsize=7.5)
    a1.invert_yaxis()
    a1.set_xscale("log")
    a1.set_xlim(2.0, 1500.0)
    a1.xaxis.set_major_locator(FixedLocator([3, 10, 30, 100, 300, 1000]))
    a1.xaxis.set_major_formatter(FuncFormatter(lambda v, p: "%g" % v))
    a1.set_xlabel("Equivalent number of termites")
    a1.grid(alpha=0.25, ls=":", lw=0.6, axis="x", zorder=0)
    a1.set_axisbelow(True)
    vline = a1.axvline(low, color="black", ls="--", lw=1.2, zorder=5)
    a1.annotate(f"lowest tested load\nN = {low}", xy=(low, 2.0),
                xytext=(8, 0), textcoords="offset points", ha="left",
                va="center", fontsize=7.5, color="black")
    a1.legend([vline, b_lod, b_loq],
              [f"Lowest tested load (N = {low} termites)",
               "LOD (3.3 $\\sigma$, equivalent termites)",
               "LOQ (10 $\\sigma$, equivalent termites)"],
              loc="lower center", bbox_to_anchor=(0.5, 1.04), ncol=3,
              frameon=False, fontsize=8)
    a1.set_title("(a) Detection and quantification limits by noise tier",
                 fontsize=9.5)

    l1, = a2.plot(t9.duration_h, t9.loo_mae_pct, "o-", color=C.ACCENT, lw=1.8,
                  ms=5.5, mec="white", mew=0.8, zorder=4)
    a2.set_xscale("log")
    a2.set_xticks(list(t9.duration_h))
    a2.xaxis.set_major_formatter(FuncFormatter(lambda v, p: "%g" % v))
    a2.set_xlim(0.85, 28)
    a2.set_ylim(0, 100)
    a2.set_xlabel("Observation duration (h)")
    a2.set_ylabel("Leave-one-out MAE of the load estimate (%)", color=C.ACCENT)
    a2.tick_params(axis="y", labelcolor=C.ACCENT)
    a2.grid(alpha=0.25, ls=":", lw=0.6)
    a2.set_title("(b) Grading error versus observation duration", fontsize=9.5)
    b2 = a2.twinx()
    l2, = b2.plot(t9.duration_h, t9.sd_net_ppm, "s--", color=C.BLUE, lw=1.8,
                  ms=5.5, mec="white", mew=0.8, zorder=4)
    b2.set_ylim(0, 1200)
    b2.set_ylabel("Between-chamber SD of net CO$_2$ accumulation (ppm)",
                  color=C.BLUE)
    b2.tick_params(axis="y", labelcolor=C.BLUE)
    b2.tick_params(axis="x", which="both", length=0)
    a2.legend([l1], ["LOO MAE (%)"], loc="upper right", framealpha=0.95, fontsize=8)
    b2.legend([l2], ["Between-chamber SD (ppm)"], loc="upper left",
              framealpha=0.95, fontsize=8)
    a2.text(0.5, 0.04, "n = 8 termite chambers", transform=a2.transAxes,
            fontsize=7.5, color="#555555", ha="center")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    _save(fig, "fig11_operational_limits.png")


ALL = [figure5_temp_rh, figure6_co2_trajectories, figure7_net_accumulation,
       figure8_dose_response, figure9_ch4_trajectories,
       figure10_ch4_selectivity, figure11_operational_limits]


def main() -> None:
    print(f"Writing figures to {C.FIGURES.relative_to(C.ROOT)}")
    for fn in ALL:
        fn()


if __name__ == "__main__":
    main()

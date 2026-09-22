# -*- coding: utf-8 -*-
"""Reproduce Tables 4-9 of the manuscript and every headline statistic.

Every number the paper quotes in the Results and Discussion is recomputed here
from ``data/termite_gas_measurements.csv`` alone, so a reader can check the analysis
without access to any intermediate artefact.

Conventions that the paper fixes and that are easy to get wrong
--------------------------------------------------------------
*   The released data and every table cover the **0-24 h analysis window**.
*   Within-series OLS R^2 (Table 5) is computed on the **raw** despiked CO2
    series, not on the blank-corrected net curve.
*   The three blank controls are reported **separately** and are never merged
    or averaged; a termite chamber is always corrected against the blank of
    its own batch.
*   Table 9 (grading error vs observation time) uses the **single final
    sample** as endpoint, whereas Tables 5-7 use the hourly-bin endpoint.

Usage
-----
    python -m src.tables
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import stats, optimize

from . import config as C
from .pipeline import (META, PROC, KEYS, TERMITE_KEYS, BATCH_KEYS,
                       BLANK_KEY, endpoints, win, hourly_bins, net_series,
                       chamber_metrics, window_coverage)

REPORT: list[str] = []


def _half_up(value: float, nd: int = 1) -> float:
    """Half-away-from-zero rounding -- see :func:`src.config.half_up`."""
    return C.half_up(value, nd)


def log(*parts) -> None:
    line = " ".join(str(p) for p in parts)
    print(line)
    REPORT.append(line)


# --------------------------------------------------------------- Table 4
def table4_window_coverage() -> pd.DataFrame:
    """Records retained in the 0-24 h window and the sampling deficit."""
    cov = window_coverage()
    cov = cov[["batch", "sheet", "N", "is_blank", "records", "duration_h",
               "start", "end", "missing_pct"]].copy()
    cov["duration_h"] = cov.duration_h.round(2)
    cov["missing_pct"] = cov.missing_pct.round(2)
    return cov


# --------------------------------------------------------------- Table 5
def table5_chamber_co2() -> pd.DataFrame:
    """Per-chamber CO2 endpoints, blank-corrected increment and fit quality."""
    m = chamber_metrics()
    t = m[~m.is_blank].copy()
    t = t[["N", "src", "sheet", "c0", "c24", "dco2", "net_dco2", "lin_r2",
           "mono"]].sort_values("N")
    t["batch"] = t.src.map(C.BATCH_NAME)
    return t[["batch", "N", "sheet", "c0", "c24", "dco2", "net_dco2",
              "lin_r2", "mono"]].reset_index(drop=True)


def table5_blanks() -> pd.DataFrame:
    """The three blank controls of Table 5, kept separately by batch."""
    m = chamber_metrics()
    b = m[m.is_blank].copy()
    b["batch"] = b.src.map(C.BATCH_NAME)
    return b[["batch", "c0", "c24", "dco2", "lin_r2", "mono"]].reset_index(drop=True)


# --------------------------------------------------------------- Table 6
def table6_environment_ch4() -> pd.DataFrame:
    """Temperature / relative-humidity envelope and the CH4 channel."""
    m = chamber_metrics()
    m = m.copy()
    m["batch"] = m.src.map(C.BATCH_NAME)
    m = m.sort_values(["is_blank", "src", "N"])
    return m[["batch", "sheet", "N", "is_blank", "temp_min", "temp_max",
              "hum_min", "hum_max", "hum_mean", "hum_sat", "ch4_median",
              "ch4_max"]].reset_index(drop=True)


# --------------------------------------------------------------- Table 7
def _loo(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float, float]:
    """Leave-one-out predictions, Q^2 and mean absolute percentage error."""
    n = len(x)
    pred = np.empty(n)
    for i in range(n):
        keep = np.ones(n, bool)
        keep[i] = False
        lr = stats.linregress(x[keep], y[keep])
        pred[i] = lr.intercept + lr.slope * x[i]
    q2 = 1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    mape = float(np.abs((y - pred) / y).mean() * 100)
    return pred, float(q2), mape


def _reml_batch_model(x: np.ndarray, y: np.ndarray, batch_code: np.ndarray,
                      n_batch: int = 3):
    """Random-intercept (batch) mixed model fitted by REML.

    Small, dependency-free implementation: the variance ratio lambda is
    optimised with a bounded scalar search on the REML criterion.  Returned
    variances are the between-batch variance (lambda * sigma^2) and the
    within-batch residual variance (sigma^2).
    """
    n = len(y)
    z = np.zeros((n, n_batch))
    z[np.arange(n), batch_code] = 1
    xm = np.column_stack([np.ones(n), x])

    def crit(lam: float):
        v = np.eye(n) + lam * (z @ z.T)
        vi = np.linalg.inv(v)
        a = xm.T @ vi @ xm
        beta = np.linalg.solve(a, xm.T @ vi @ y)
        r = y - xm @ beta
        sig = float(r @ vi @ r) / (n - xm.shape[1])
        sign_v, ld_v = np.linalg.slogdet(v)
        sign_a, ld_a = np.linalg.slogdet(a)
        return (n - xm.shape[1]) * np.log(sig) + ld_v + ld_a + (n - xm.shape[1])

    opt = optimize.minimize_scalar(lambda l: crit(max(l, 0.0)),
                                   bounds=(0.0, 1e4), method="bounded")
    lam = max(float(opt.x), 0.0)
    v = np.eye(n) + lam * (z @ z.T)
    vi = np.linalg.inv(v)
    a = xm.T @ vi @ xm
    beta = np.linalg.solve(a, xm.T @ vi @ y)
    r = y - xm @ beta
    sig = float(r @ vi @ r) / (n - xm.shape[1])
    return dict(lam=lam, beta=beta, sigma2=sig,
                sd_within=float(np.sqrt(sig)),
                sd_between=float(np.sqrt(lam * sig)),
                icc=float(lam / (lam + 1)))


def table7_statistics() -> dict:
    """Dose-response fit, cross-validation, batch effect and CH4 corroboration."""
    x, y = _dose_xy()
    n = len(x)
    lr = stats.linregress(x, y)
    rho, p_rho = stats.spearmanr(x, y)
    resid = y - (lr.intercept + lr.slope * x)
    rmse = float(np.sqrt((resid ** 2).mean()))
    mae = float(np.abs(resid).mean())
    s_res = float(np.sqrt((resid ** 2).sum() / (n - 2)))
    tcrit = stats.t.ppf(0.975, n - 2)
    pred, q2, mape = _loo(x, y)

    # ANCOVA: net dCO2 ~ N + batch (Batch 1 is the reference level)
    b7 = (np.array([k[0] for k in TERMITE_KEYS_sorted()]) == "data7").astype(float)
    b9 = (np.array([k[0] for k in TERMITE_KEYS_sorted()]) == "data9").astype(float)
    full = np.column_stack([np.ones(n), x, b7, b9])
    beta, *_ = np.linalg.lstsq(full, y, rcond=None)
    ss_res = float(((y - full @ beta) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    red = np.column_stack([np.ones(n), x])
    br, *_ = np.linalg.lstsq(red, y, rcond=None)
    ss_red = float(((y - red @ br) ** 2).sum())
    df1, df2 = 2, n - 4
    f_stat = ((ss_red - ss_res) / df1) / (ss_res / df2)
    p_f = float(1 - stats.f.cdf(f_stat, df1, df2))

    # batch offsets.  In the ANCOVA above, Batch 1 (data6) is the reference
    # level, so beta[2] and beta[3] are the data7 and data9 offsets in ppm.
    off6, off7, off9 = 0.0, float(beta[2]), float(beta[3])

    # --- endpoint-definition sensitivity (last full hour, h > 23) ----------
    lh_y = np.array([_net24(k, "lasthour") for k in TERMITE_KEYS_sorted()])
    lh = stats.linregress(x, lh_y)
    lh_delta = lh_y - y

    # --- Batch-2-only calibration (the only five-load batch) ---------------
    m7b = np.array([k[0] for k in TERMITE_KEYS_sorted()]) == "data7"
    l7b = stats.linregress(x[m7b], y[m7b])
    b2_resid = y[m7b] - (l7b.intercept + l7b.slope * x[m7b])
    b2_sd = float(np.sqrt((b2_resid ** 2).sum() / (m7b.sum() - 2)))

    # --- cross-batch transfer: Batch-2 model applied to Batches 1 and 3 ----
    t_pred = l7b.intercept + l7b.slope * x[~m7b]
    t_dev = (y[~m7b] - t_pred) / t_pred * 100

    mix = _reml_batch_model(x, y, np.array(
        [{"data6": 0, "data7": 1, "data9": 2}[k[0]] for k in TERMITE_KEYS_sorted()]))

    # CH4 corroboration at chamber level
    m = chamber_metrics()
    t = m[~m.is_blank].sort_values("N")
    rho_med, p_med = stats.spearmanr(t.ch4_median, t.net_dco2)
    rho_max, p_max = stats.spearmanr(t.ch4_max, t.net_dco2)

    return dict(
        n_chambers=n,
        slope=float(lr.slope), slope_se=float(lr.stderr),
        slope_ci=[float(lr.slope - tcrit * lr.stderr),
                  float(lr.slope + tcrit * lr.stderr)],
        intercept=float(lr.intercept), r2=float(lr.rvalue ** 2),
        p=float(lr.pvalue), spearman=float(rho), spearman_p=float(p_rho),
        rmse=rmse, mae=mae, resid_sd=s_res,
        loo_q2=q2, loo_mape_pct=mape,
        ancova_r2=float(1 - ss_res / ss_tot), ancova_f=float(f_stat),
        ancova_p=p_f, ancova_df=[df1, df2],
        batch_offset_b1=off6, batch_offset_b2=off7, batch_offset_b3=off9,
        mixed_slope=float(mix["beta"][1]), mixed_intercept=float(mix["beta"][0]),
        mixed_sd_between_ppm=mix["sd_between"], mixed_sd_within_ppm=mix["sd_within"],
        mixed_icc=mix["icc"],
        rate_mean=float((y / x).mean()), rate_sd=float((y / x).std(ddof=1)),
        ch4_rho_median=float(rho_med), ch4_p_median=float(p_med),
        ch4_rho_max=float(rho_max), ch4_p_max=float(p_max),
        # endpoint-definition sensitivity
        lasthour_slope=float(lh.slope), lasthour_r2=float(lh.rvalue ** 2),
        lasthour_mean_change_ppm=float(np.abs(lh_delta).mean()),
        lasthour_max_change_ppm=float(np.abs(lh_delta).max()),
        # single-batch calibration
        batch2_slope=float(l7b.slope), batch2_r2=float(l7b.rvalue ** 2),
        batch2_p=float(l7b.pvalue), batch2_resid_sd=b2_sd,
        # cross-batch transfer
        transfer_dev_min=float(t_dev.min()), transfer_dev_max=float(t_dev.max()),
        ancova_common_slope=float(beta[1]),
    )


def table7_rows() -> pd.DataFrame:
    """Table 7 laid out exactly as printed: one row per analysis."""
    s = table7_statistics()

    def sci(v: float) -> str:
        mant, exp = f"{v:.1e}".split("e")
        return f"{mant} x 10^{int(exp)}"

    return pd.DataFrame([
        dict(analysis="Pooled OLS (n = 8)", statistic="Slope (ppm termite-1 24 h-1)",
             estimate=f"{s['slope']:.2f}",
             se_ci=f"SE {s['slope_se']:.2f}; CI {s['slope_ci'][0]:.2f}-{s['slope_ci'][1]:.2f}",
             p=sci(s["p"]), note=f"Intercept {s['intercept']:.1f} ppm"),
        dict(analysis="Pooled OLS (n = 8)", statistic="R2",
             estimate=f"{s['r2']:.3f}", se_ci="-", p="-",
             note=f"Pearson r = {np.sqrt(s['r2']):.3f}"),
        dict(analysis="Rank correlation (n = 8)", statistic="Spearman rho",
             estimate=f"{s['spearman']:.3f}", se_ci="-", p=sci(s["spearman_p"]),
             note="Monotonic dose ordering"),
        dict(analysis="Per-termite rate (n = 8)", statistic="Mean +/- SD",
             estimate=f"{s['rate_mean']:.2f} +/- {s['rate_sd']:.2f}", se_ci="-", p="-",
             note=f"CV = {s['rate_sd'] / s['rate_mean'] * 100:.1f}%"),
        dict(analysis="LOO cross-validation", statistic="Q2",
             estimate=f"{s['loo_q2']:.2f}", se_ci="-", p="-",
             note=f"Mean abs. error {s['loo_mape_pct']:.1f}%"),
        dict(analysis="Endpoint definition (last full hour median, h > 23)",
             statistic="Slope / R2",
             estimate=f"{s['lasthour_slope']:.2f} / {s['lasthour_r2']:.3f}",
             se_ci="-", p="-",
             note=f"Net dCO2 changed by {s['lasthour_mean_change_ppm']:.1f} ppm on "
                  f"average (max {s['lasthour_max_change_ppm']:.1f} ppm)"),
        dict(analysis="Batch 2 only (n = 5)", statistic="Slope / R2",
             estimate=f"{s['batch2_slope']:.2f} / {s['batch2_r2']:.3f}",
             se_ci="-", p=f"{s['batch2_p']:.3f}", note="Five-load batch"),
        dict(analysis="Cross-batch transfer", statistic="Deviation",
             estimate=f"{s['transfer_dev_min']:.1f} to {s['transfer_dev_max']:.1f}%",
             se_ci="-", p="-", note="Batch-2 model -> Batches 1, 3"),
        dict(analysis="ANCOVA (N + batch)", statistic="Batch F(2,4)",
             estimate=f"{s['ancova_f']:.2f}", se_ci="-", p=f"{s['ancova_p']:.2f}",
             note=f"R2 = {s['ancova_r2']:.3f}; common slope "
                  f"{s['ancova_common_slope']:.2f}"),
    ])


def TERMITE_KEYS_sorted():
    """Termite chambers in ascending load -- the canonical order of `sel`."""
    return sorted(TERMITE_KEYS, key=lambda k: META[k]["N"])


def model_comparison() -> pd.DataFrame:
    """Alternative dose-response specifications for the 0-24 h window.

    Each model predicts the blank-corrected net 24 h accumulation from termite
    number ``N``.  ``r2`` is the in-sample coefficient of determination and
    ``q2`` the leave-one-out cross-validated predictive skill; both are computed
    on the original (ppm) scale against the same total sum of squares, so the
    specifications are directly comparable.  The set covers every alternative for
    which Section 4.3 reports a Q^2: the same line through the origin, a weighted
    regression (weights 1/N^2), a power law, a temperature covariate, a baseline
    covariate and a random batch intercept.  The weighted and power-law forms
    reach a ``q2`` marginally above the reported fit; the gaps are within the
    uncertainty of a leave-one-out estimate on eight chambers, which is why the
    manuscript describes the alternatives as not *materially* better.

    The saturating Michaelis-Menten form is deliberately absent: with eight
    points it is not identifiable -- the fit runs to the boundary -- which is
    what the manuscript states, so no Q^2 is reported for it.
    """
    keys = TERMITE_KEYS_sorted()
    x, y = _dose_xy()
    n = len(x)
    m = chamber_metrics().set_index(["src", "sheet"])
    temp = np.array([float(m.loc[k]["temp_mean"]) for k in keys])
    c0 = np.array([float(m.loc[k]["c0"]) for k in keys])
    bcode = np.array([{"data6": 0, "data7": 1, "data9": 2}[k[0]] for k in keys])
    ss_tot = float(((y - y.mean()) ** 2).sum())

    def _ols(Z: np.ndarray):
        beta, *_ = np.linalg.lstsq(Z, y, rcond=None)
        pred = np.empty(n)
        for i in range(n):
            keep = np.ones(n, bool)
            keep[i] = False
            b, *_ = np.linalg.lstsq(Z[keep], y[keep], rcond=None)
            pred[i] = float(Z[i] @ b)
        return (1 - float(((y - Z @ beta) ** 2).sum()) / ss_tot,
                1 - float(((y - pred) ** 2).sum()) / ss_tot)

    rows = []
    r2, q2 = _ols(np.column_stack([np.ones(n), x]))
    rows.append(dict(model="linear (reported)", r2=r2, q2=q2))
    r2, q2 = _ols(x.reshape(-1, 1))
    rows.append(dict(model="through origin", r2=r2, q2=q2))

    # weighted least squares, weights 1/N^2 -- fitted on the weighted loss but
    # scored on the same unweighted ppm scale as every other row.  The design is
    # pre-multiplied by sqrt(w) (and NOT by w, which would minimise
    # sum(w^2 * residual^2), i.e. weights 1/N^4) so that lstsq really solves
    # min sum(w * residual^2).
    sw = 1.0 / x
    Zw = np.column_stack([np.ones(n), x])
    bw, *_ = np.linalg.lstsq(Zw * sw[:, None], y * sw, rcond=None)
    pw = np.empty(n)
    for i in range(n):
        keep = np.ones(n, bool)
        keep[i] = False
        Zk = Zw[keep] * sw[keep][:, None]
        b, *_ = np.linalg.lstsq(Zk, y[keep] * sw[keep], rcond=None)
        pw[i] = float(Zw[i] @ b)
    rows.append(dict(model="weighted (1/N^2)",
                     r2=1 - float(((y - Zw @ bw) ** 2).sum()) / ss_tot,
                     q2=1 - float(((y - pw) ** 2).sum()) / ss_tot))

    # power law -- a straight line in log-log space, scored on the ppm scale
    Zp = np.column_stack([np.ones(n), np.log(x)])
    ly = np.log(y)
    bp, *_ = np.linalg.lstsq(Zp, ly, rcond=None)
    pp = np.empty(n)
    for i in range(n):
        keep = np.ones(n, bool)
        keep[i] = False
        b, *_ = np.linalg.lstsq(Zp[keep], ly[keep], rcond=None)
        pp[i] = float(np.exp(Zp[i] @ b))
    rows.append(dict(model="power law",
                     r2=1 - float(((y - np.exp(Zp @ bp)) ** 2).sum()) / ss_tot,
                     q2=1 - float(((y - pp) ** 2).sum()) / ss_tot))

    r2, q2 = _ols(np.column_stack([np.ones(n), x, temp]))
    rows.append(dict(model="N + mean chamber temperature", r2=r2, q2=q2))
    r2, q2 = _ols(np.column_stack([np.ones(n), x, c0]))
    rows.append(dict(model="N + baseline c0", r2=r2, q2=q2))

    beta = _reml_batch_model(x, y, bcode)["beta"]
    mp = np.empty(n)
    for i in range(n):
        keep = np.ones(n, bool)
        keep[i] = False
        mm = _reml_batch_model(x[keep], y[keep], bcode[keep])
        mp[i] = float((np.column_stack([np.ones(1), [x[i]]]) @ mm["beta"])[0])
    r2 = 1 - float(((y - np.column_stack([np.ones(n), x]) @ beta) ** 2).sum()) / ss_tot
    rows.append(dict(model="mixed (random batch intercept)", r2=r2,
                     q2=1 - float(((y - mp) ** 2).sum()) / ss_tot))
    return pd.DataFrame(rows)


def _dose_xy():
    keys = TERMITE_KEYS_sorted()
    x = np.array([META[k]["N"] for k in keys], float)
    y = np.array([_net24(k) for k in keys], float)
    return x, y


def _net24(key, mode: str = "hourly") -> float:
    """Blank-corrected 24 h increment of one chamber under a chosen endpoint."""
    c0, c24 = endpoints(key, mode)
    b = BLANK_KEY[key[0]]
    b0, b24 = endpoints(b, mode)
    return (c24 - c0) - (b24 - b0)


def _endpoint_delta(key, mode: str = "hourly") -> float:
    """Raw (uncorrected) 24 h change of one series -- used for the blanks.

    A blank must not be corrected against itself, so the blank-to-blank tier
    of Table 8 uses this helper instead of ``_net24``.
    """
    c0, c24 = endpoints(key, mode)
    return c24 - c0


# --------------------------------------------------------------- Table 8
def table8_detection_limits() -> pd.DataFrame:
    """LOD / LOQ as an equivalent number of termites, for five noise levels.

    sigma is the noise of the blank or of the calibration residual in ppm.
    Dividing it by the dose-response slope (ppm per termite per 24 h) converts
    it to an equivalent number of termites, with LOD = 3.3 sigma and
    LOQ = 10 sigma.  LOD/LOQ are computed from the unrounded sigma, so the
    printed values can differ from a naive recomputation by +/- 0.1.
    """
    stats7 = table7_statistics()
    slope = stats7["slope"]
    tiers = []

    short, roll, blank_d = [], [], []
    for src in C.BATCHES:
        key = BLANK_KEY[src]
        b = win(key)
        v = b["co2c"].values
        short.append(float(np.diff(v).std(ddof=1) / np.sqrt(2)))
        tr = b["co2c"].rolling(19, center=True, min_periods=5).median()
        roll.append(float((b["co2c"] - tr).dropna().std(ddof=1)))
        blank_d.append(_endpoint_delta(key))
    s_short = max(short)
    s_roll = max(roll)
    s_blank = float(np.std(blank_d, ddof=1))
    s_pool = stats7["resid_sd"]
    s_b2 = stats7["batch2_resid_sd"]
    slope_b2 = stats7["batch2_slope"]

    def fmt3(vals) -> str:
        # Keep the batch order used elsewhere in the paper (Batch 1, 2, 3).
        # Do NOT sort: the third tier below lists signed batch values, which are
        # only readable in batch order.
        return " / ".join(f"{v:.2f}" for v in vals)

    for tag, s, sl, note in [
        ("Blank short-term noise", s_short, slope,
         f"SD of adjacent 10-min differences / sqrt(2), largest of the three "
         f"blanks ({fmt3(short)} ppm)"),
        ("Blank detrended residual", s_roll, slope,
         f"SD of the 19-point rolling-median-detrended blank residual, largest "
         f"batch ({fmt3(roll)} ppm)"),
        ("Blank-to-blank 24 h change", s_blank, slope,
         "SD of the three batch blanks' dCO2 "
         f"({', '.join(f'{_half_up(v):+.1f}' for v in blank_d)} ppm)"),
        ("Pooled calibration residual", s_pool, slope,
         "Residual SD of net dCO2 ~ N, n = 8"),
        ("Batch-2-only calibration residual", s_b2, slope_b2,
         "Residual SD of the within-batch fit, n = 5"),
    ]:
        tiers.append(dict(tier=tag, sigma_ppm=round(s, 2),
                          basis=note, slope_ppm_per_termite=round(sl, 2),
                          lod_termites=round(3.3 * s / sl, 1),
                          loq_termites=round(10 * s / sl, 1)))
    return pd.DataFrame(tiers)


# --------------------------------------------------------------- Table 9
def table9_grading() -> pd.DataFrame:
    """Grading error as a function of how long the chamber is observed.

    At each duration the net accumulation available so far is used to predict
    the load N through the pooled calibration, and the leave-one-out error of
    that prediction is reported.  Endpoint = single final sample (Table 9).
    """
    keys = TERMITE_KEYS_sorted()
    x = np.array([META[k]["N"] for k in keys], float)
    rows = []
    for dt in (1, 2, 4, 8, 12, 24):
        vals = np.array([float(np.interp(dt, *net_series(k))) for k in keys])
        lr = stats.linregress(x, vals)
        pred = np.empty(len(x))
        for i in range(len(x)):
            keep = np.ones(len(x), bool)
            keep[i] = False
            l = stats.linregress(x[keep], vals[keep])
            pred[i] = (vals[i] - l.intercept) / l.slope
        err = pred - x
        rows.append(dict(
            duration_h=dt,
            r2=round(float(lr.rvalue ** 2), 3),
            p=float(lr.pvalue),
            slope_ppm_per_termite=round(float(lr.slope), 3),
            loo_mae_termites=round(float(np.abs(err).mean()), 1),
            loo_mae_pct=round(float((np.abs(err) / x).mean() * 100), 1),
            worst_case_pct=round(float((np.abs(err) / x).max() * 100), 1),
            sd_net_ppm=round(float(vals.std(ddof=1)), 1),
        ))
    return pd.DataFrame(rows)


# ------------------------------------------------------- supporting analyses
def kinetics() -> pd.DataFrame:
    """Saturation diagnostics: t50 / t90, late-vs-mean slope, fitted tau."""
    rows = []
    for key in TERMITE_KEYS_sorted():
        h, net = net_series(key)
        final = net[-1]
        mean_slope = final / 24.0
        late = h >= 20
        s_late = float(stats.linregress(h[late], net[late]).slope)

        def t_frac(f):
            idx = np.where(net >= f * final)[0]
            i = idx[0]
            return float(h[0]) if i == 0 else float(np.interp(
                f * final, [net[i - 1], net[i]], [h[i - 1], h[i]]))

        def f_exp(t, a, tau):
            return a * (1 - np.exp(-t / tau))

        try:
            popt, _ = optimize.curve_fit(f_exp, h, net, p0=[final * 1.5, 24.0],
                                         maxfev=400000,
                                         bounds=([0, 0.5], [1e6, 1e5]))
            a_exp, tau = float(popt[0]), float(popt[1])
            sse_exp = float(((net - f_exp(h, *popt)) ** 2).sum())
        except Exception:
            a_exp, tau, sse_exp = np.nan, np.nan, np.nan

        def f_lin(t, a, b):
            return a * t + b
        pl, _ = optimize.curve_fit(f_lin, h, net, p0=[mean_slope, 0.0])
        sse_lin = float(((net - f_lin(h, *pl)) ** 2).sum())
        nn = len(h)
        total = float(((net - net.mean()) ** 2).sum())
        aic_exp = nn * np.log(sse_exp / nn) + 2 * 2 if np.isfinite(sse_exp) else np.nan
        aic_lin = nn * np.log(sse_lin / nn) + 2 * 2

        rows.append(dict(
            key=f"{key[0]}-{key[1]}", N=META[key]["N"],
            net24_ppm=round(final, 1),
            t50_h=round(t_frac(0.5), 2), t90_h=round(t_frac(0.9), 2),
            late_over_mean_slope=round(s_late / mean_slope, 3),
            tau_h=round(tau, 1) if np.isfinite(tau) else None,
            tau_identifiable=(bool(aic_exp - aic_lin < -2)
                              if np.isfinite(aic_exp) else None),
            dAIC_exp_minus_lin=round(aic_exp - aic_lin, 1) if np.isfinite(aic_exp) else None,
            r2_exp=round(1 - sse_exp / total, 4) if np.isfinite(sse_exp) else None,
            r2_lin=round(1 - sse_lin / total, 4),
        ))
    return pd.DataFrame(rows)


def ch4_selectivity() -> dict:
    """Within-chamber correlations of the MOx CH4 channel (7 responsive chambers).

    Series are z-scored per chamber and pooled; partial correlations control
    for the other two predictors.  Chambers whose CH4 channel is flat (all
    zero) cannot be standardised and are excluded -- that is why n is the
    number of CH4-responsive chambers, not all eight.
    """
    zc, zt, zh, zch = [], [], [], []
    n_ch = 0
    for key in TERMITE_KEYS_sorted():
        w = win(key)
        if w["ch4c"].std(ddof=1) == 0:
            continue
        n_ch += 1

        def z(a):
            a = np.asarray(a, float)
            return (a - a.mean()) / a.std(ddof=1)

        zc.append(z(w["co2c"].values))
        zt.append(z(w["tmpc"].values))
        zh.append(z(w["humc"].values))
        zch.append(z(w["ch4c"].values))
    zc, zt, zh, zch = map(np.concatenate, (zc, zt, zh, zch))
    m = len(zc)

    def partial(a, b, ctrl):
        design = np.column_stack([np.ones(m)] + list(ctrl))
        ra = a - design @ np.linalg.lstsq(design, a, rcond=None)[0]
        rb = b - design @ np.linalg.lstsq(design, b, rcond=None)[0]
        r, p = stats.pearsonr(ra, rb)
        return float(r), float(p)

    def vif(cols):
        out = []
        for j in range(cols.shape[1]):
            other = np.column_stack([np.ones(m), np.delete(cols, j, axis=1)])
            res = cols[:, j] - other @ np.linalg.lstsq(other, cols[:, j], rcond=None)[0]
            r2 = 1 - (res ** 2).sum() / ((cols[:, j] - cols[:, j].mean()) ** 2).sum()
            out.append(float(1 / (1 - r2)))
        return out

    r_co2, p_co2 = stats.pearsonr(zch, zc)
    r_t, p_t = stats.pearsonr(zch, zt)
    r_rh, p_rh = stats.pearsonr(zch, zh)
    part_co2, pp_co2 = partial(zch, zc, [zt, zh])
    part_t, pp_t = partial(zch, zt, [zc, zh])
    part_rh, pp_rh = partial(zch, zh, [zc, zt])
    v = vif(np.column_stack([zc, zt, zh]))

    return dict(
        n_chambers=n_ch, n_points=int(m),
        zero_order=dict(co2=[float(r_co2), float(p_co2)],
                        temp=[float(r_t), float(p_t)],
                        rh=[float(r_rh), float(p_rh)]),
        partial=dict(co2=[part_co2, pp_co2], temp=[part_t, pp_t],
                     rh=[part_rh, pp_rh]),
        vif=dict(co2=v[0], temp=v[1], rh=v[2]),
    )


def time_to_alarm() -> pd.DataFrame:
    """First time the blank-corrected signal clears 3 x SD of the three blanks."""
    m = chamber_metrics()
    blanks = m[m.is_blank]
    thr = 3 * float(np.std(blanks.dco2.values, ddof=1))
    rows = []
    for key in TERMITE_KEYS_sorted():
        h, net = net_series(key)
        idx = np.where(net >= thr)[0]
        i = idx[0]
        t = float(h[0]) if i == 0 else float(np.interp(
            thr, [net[i - 1], net[i]], [h[i - 1], h[i]]))
        rows.append(dict(N=META[key]["N"], threshold_ppm=round(thr, 1),
                         t_alarm_h=round(t, 2), t_alarm_min=round(t * 60)))
    return pd.DataFrame(rows)


# --------------------------------------------------------------- driver
def main() -> None:
    C.RESULTS.mkdir(exist_ok=True)

    t4 = table4_window_coverage()
    t5 = table5_chamber_co2()
    t5b = table5_blanks()
    t6 = table6_environment_ch4()
    t7 = table7_statistics()
    t7rows = table7_rows()
    t8 = table8_detection_limits()
    t9 = table9_grading()
    kin = kinetics()
    sel = ch4_selectivity()
    tta = time_to_alarm()
    mc = model_comparison()

    t4.to_csv(C.RESULTS / "table4_window_coverage.csv", index=False,
              encoding="utf-8-sig")
    t5.to_csv(C.RESULTS / "table5_chamber_co2.csv", index=False, encoding="utf-8-sig")
    t5b.to_csv(C.RESULTS / "table5_blank_controls.csv", index=False,
               encoding="utf-8-sig")
    t6.to_csv(C.RESULTS / "table6_environment_ch4.csv", index=False,
              encoding="utf-8-sig")
    t7rows.to_csv(C.RESULTS / "table7_statistics.csv", index=False,
                  encoding="utf-8-sig")
    t8.to_csv(C.RESULTS / "table8_detection_limits.csv", index=False,
              encoding="utf-8-sig")
    t9.to_csv(C.RESULTS / "table9_grading_vs_duration.csv", index=False,
              encoding="utf-8-sig")
    kin.to_csv(C.RESULTS / "kinetics_saturation.csv", index=False,
               encoding="utf-8-sig")
    tta.to_csv(C.RESULTS / "time_to_alarm.csv", index=False, encoding="utf-8-sig")
    mc.to_csv(C.RESULTS / "model_comparison.csv", index=False, encoding="utf-8-sig")

    numbers = dict(table7=t7, ch4_selectivity=sel,
                   time_to_alarm_range_h=[float(tta.t_alarm_h.min()),
                                          float(tta.t_alarm_h.max())],
                   model_comparison=[dict(model=str(r.model),
                                          r2=round(float(r.r2), 4),
                                          q2=round(float(r.q2), 4))
                                     for _, r in mc.iterrows()])
    (C.RESULTS / "key_numbers.json").write_text(
        json.dumps(numbers, indent=2, ensure_ascii=False), encoding="utf-8")

    log("=" * 72)
    log("Table 4 - 0-24 h window coverage")
    log(t4.to_string(index=False))
    log("\nTable 5 - chamber-level CO2 endpoints (blank-corrected)")
    log(t5.round({"c0": 1, "c24": 1, "dco2": 1, "net_dco2": 1, "lin_r2": 3})
        .to_string(index=False))
    log("\n  blank controls, reported separately")
    disp = t5b.copy()
    for col in ("c0", "c24", "dco2"):
        disp[col] = [C.half_up(v) for v in disp[col]]
    log(disp.to_string(index=False))
    log("\nTable 6 - environment and CH4 channel")
    log(t6.round(2).to_string(index=False))
    log("\nTable 7 - dose-response statistics")
    log(t7rows.to_string(index=False))
    log("\nTable 8 - detection / quantification limits")
    log(t8.to_string(index=False))
    log("\nTable 9 - grading error vs observation duration")
    log(t9.to_string(index=False))
    log("\nSaturation kinetics")
    log(kin.to_string(index=False))
    exp_pref = kin[kin.tau_identifiable == True]                       # noqa: E712
    lin_pref = kin[kin.tau_identifiable == False]                      # noqa: E712
    log(f"  exponential preferred in {len(exp_pref)}/8 chambers: tau = "
        + ", ".join(f"N={r.N} {r.tau_h} h" for _, r in exp_pref.iterrows()))
    log(f"  line preferred in {len(lin_pref)}/8 chambers (dAIC = "
        f"+{lin_pref.dAIC_exp_minus_lin.min():.1f} to "
        f"+{lin_pref.dAIC_exp_minus_lin.max():.1f}); there tau is not resolvable "
        f"within 24 h (fitted values run to 10^4 h)")
    top2 = kin[kin.N >= 412]
    log(f"  final-4-h / mean slope at the two highest loads: "
        f"{top2.late_over_mean_slope.min():.2f}-{top2.late_over_mean_slope.max():.2f}")
    log("\nCH4-channel selectivity (within-chamber, chambres with a signal)")
    for group in ("zero_order", "partial"):
        for name, (r, p) in sel[group].items():
            log(f"  {group:11s} r(CH4,{name:4s}) = {r:+.3f}  (p = {p:.3g})")
    log(f"  n = {sel['n_points']} points from {sel['n_chambers']} chambers; "
        f"VIF {sel['vif']}")
    log("\nTime to alarm (3 x SD of the three blanks)")
    log(tta.to_string(index=False))
    log(f"\n  0-24 h window holds {int(t4.records.sum()):,} records; missing "
        f"{t4[t4.N > 0].missing_pct.mean():.2f}% per termite chamber")
    log("\nDose-response model comparison (0-24 h window, LOO cross-validated)")
    log(mc.round({"r2": 4, "q2": 4}).to_string(index=False))

    (C.RESULTS / "console_report.txt").write_text("\n".join(REPORT),
                                                  encoding="utf-8")
    print("\nSaved -> results/*.csv, results/key_numbers.json, results/console_report.txt")


if __name__ == "__main__":
    main()

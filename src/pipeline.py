# -*- coding: utf-8 -*-
"""Preprocessing pipeline.

The preprocessing is deliberately simple and is applied identically to every
series, so that the dose-response reported in the paper can be reproduced from
the released data alone:

    raw minute values
      -> 7-point rolling median-absolute-deviation despiking (k = 6)
      -> 10-minute median resampling
      -> 0-24 h analysis window
      -> c0 = median of the first hourly bin, c24 = value of the last hourly bin
      -> dCO2 = c24 - c0
      -> net dCO2 = dCO2(chamber) - dCO2(batch-paired blank control)

Two conventions matter for reproducing the paper and are easy to get wrong:

1.  Within-series OLS R^2 in Table 5 is computed on the *raw* (despiked,
    resampled) CO2 series, not on the blank-corrected net curve.
2.  Table 9 (grading error versus observation time) uses a *single final
    sample* as the endpoint, whereas Tables 5-7 use the hourly-bin endpoint
    above. Both definitions are provided by `endpoints()`.

Run as a script to print a short digest of the loaded dataset.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from . import config as C

# ---------------------------------------------------------------- despiking
def despike(values, win: int = C.DESPIKE_WIN, k: float = C.DESPIKE_K) -> pd.Series:
    """Rolling median-absolute-deviation despiker.

    Points deviating from the centred rolling median by more than ``k`` scaled
    MADs are set to NaN and then linearly interpolated. The scaled MAD
    (1.4826 * MAD) is a consistent estimator of sigma for normal noise; the
    lower clip at 1 ppm keeps the filter from collapsing on flat signals.
    """
    s = pd.Series(np.asarray(values, dtype="float64"))
    med = s.rolling(win, center=True, min_periods=1).median()
    mad = (s - med).abs().rolling(win, center=True, min_periods=1).median()
    s[(s - med).abs() > k * (1.4826 * mad).clip(lower=1)] = np.nan
    return s.interpolate(limit_direction="both")


CHANNELS = {"co2": "co2c", "ch4": "ch4c", "temp": "tmpc", "hum": "humc"}


# ---------------------------------------------------------------- loading
def _parse_series_time(strings, year: int = C.YEAR_ASSUMED):
    """Parse the original ``MM-DD HH:MM`` stamps, which carry no year.

    The year is filled in and incremented whenever the month-day-time sequence
    steps backwards, so a run that crosses midnight (or New Year) still yields
    a monotonic axis.  Only relative durations are ever reported from it.
    """
    out, prev, y = [], None, year
    for s in strings:
        t = pd.Timestamp(f"{y}-{str(s).strip()}")
        if prev is not None and t < prev:
            y += 1
            t = pd.Timestamp(f"{y}-{str(s).strip()}")
        out.append(t)
        prev = t
    return out


def load_long(path=None) -> pd.DataFrame:
    """Read the measurements file and return the tidy long table.

    The file is one flat table: a single header row followed by one row per
    sample.  Which chamber a row belongs to is carried by the ``Chamber (N)``
    column, which uses the manuscript's Table 5 notation -- ``Batch 1 · 310``
    for a termite chamber and ``Batch 1 · Blank (0)`` for a blank control.
    This function splits that label into a batch and a condition, derives the
    termite number, and builds the elapsed-hours axis of each chamber.
    """
    path = Path(path) if path else C.MEASUREMENTS_CSV
    raw = pd.read_csv(path, dtype=str, encoding="utf-8-sig",
                      keep_default_na=False)

    missing = [h for h in C.HEADER if h not in raw.columns]
    if missing:
        raise ValueError(f"{path}: missing column(s) {missing}; "
                         f"expected {C.HEADER}")

    parts = raw[C.CHAMBER_COL].str.partition(C.CHAMBER_SEP)
    batch_label = parts[0].str.strip()
    condition = parts[2].str.strip()
    if (parts[1] == "").any():
        raise ValueError(f"{path}: malformed {C.CHAMBER_COL} label(s), "
                         f"expected '<batch>{C.CHAMBER_SEP}<condition>'")

    df = pd.DataFrame({short: raw[col].str.strip()
                       for col, short in C.FIELDS.items()})
    for short in ("co2", "temp", "hum", "ch4"):
        df[short] = pd.to_numeric(df[short])

    df["src"] = batch_label.map(C.SRC_OF_BATCH)
    if df["src"].isna().any():
        bad = sorted(set(batch_label[df["src"].isna()]))
        raise ValueError(f"unrecognised batch label(s): {bad}")
    df["sheet"] = condition
    df["N"] = np.where(
        condition == C.BLANK_CONDITION, 0,
        pd.to_numeric(condition.str.extract(r"^(\d+)$", expand=False),
                      errors="coerce")).astype("int64")
    df["is_blank"] = df["N"] == 0
    df["t"] = pd.concat(
        [pd.Series(_parse_series_time(g["timestr"].tolist()), index=g.index)
         for _, g in df.groupby(["src", "sheet"], sort=False)])
    df = df.sort_values(["src", "sheet", "t"]).reset_index(drop=True)
    df["h"] = df.groupby(["src", "sheet"], sort=False)["t"].transform(
        lambda s: (s - s.iloc[0]).dt.total_seconds() / 3600.0)
    return df


def _build(long: pd.DataFrame):
    proc, meta = {}, {}
    for (src, sheet), g in long.groupby(["src", "sheet"], sort=True):
        g = g.sort_values("t").reset_index(drop=True)
        for raw, clean_name in CHANNELS.items():
            g[clean_name] = despike(g[raw].values)
        r = (g.set_index("t")[list(CHANNELS.values())]
               .resample(C.RESAMPLE).median())
        r["h"] = (r.index - r.index[0]).total_seconds() / 3600.0
        key = (src, str(sheet))
        proc[key] = r
        meta[key] = dict(
            key=key, src=src, sheet=str(sheet),
            N=int(g["N"].iloc[0]),
            is_blank=bool(g["is_blank"].iloc[0]),
            n_records=int(len(g)),
            duration_h=float(g["h"].max()),
            t_start=str(g["timestr"].iloc[0]),
            t_end=str(g["timestr"].iloc[-1]),
        )
    return proc, meta


LONG = load_long()
PROC, META = _build(LONG)

KEYS = sorted(PROC.keys(), key=lambda k: (k[0], META[k]["N"]))
TERMITE_KEYS = [k for k in KEYS if not META[k]["is_blank"]]
BATCH_KEYS = {src: [k for k in KEYS if k[0] == src] for src in C.BATCHES}
BLANK_KEY = {src: (src, C.BLANK_CONDITION) for src in C.BATCHES}

N_BY_KEY = {k: META[k]["N"] for k in KEYS}


# ---------------------------------------------------------------- accessors
def win(key, hmax: float = C.WINDOW_H) -> pd.DataFrame:
    """The 0-hmax window of one processed series (10-minute resolution)."""
    r = PROC[key]
    return r[(r.h >= 0) & (r.h <= hmax)]


def hourly_bins(w: pd.DataFrame) -> pd.Series:
    """Median per integer hour; the final bin holds a single 10-min sample."""
    return w.groupby(np.floor(w.h))["co2c"].median()


def endpoints(key, mode: str = "hourly"):
    """(c0, c24) CO2 endpoints of one chamber under a chosen definition.

    mode = "hourly"   first hourly-bin median  /  value of the last hourly bin
                      (the definition used in Tables 5-7)
    mode = "lasthour" first hourly-bin median  /  median of the last full hour
                      (sensitivity check reported in Section 4.3)
    mode = "sample"   first sample             /  final sample
                      (the definition behind Table 9)
    """
    w = win(key)
    if mode == "hourly":
        hr = hourly_bins(w)
        return float(hr.iloc[0]), float(hr.iloc[-1])
    if mode == "lasthour":
        hr = hourly_bins(w)
        return float(hr.iloc[0]), float(w[w.h > 23]["co2c"].median())
    if mode == "sample":
        return float(w["co2c"].iloc[0]), float(w["co2c"].iloc[-1])
    raise ValueError(f"unknown endpoint mode: {mode!r}")


def net_series(key, hmax: float = C.WINDOW_H):
    """Blank-corrected net CO2 accumulation curve, zeroed at h = 0.

    The blank control of the *same batch* is subtracted pointwise, so blank
    drift (which differs in sign between batches) is removed without merging
    the three blanks.
    """
    src = key[0]
    w = win(key, hmax)
    b = win(BLANK_KEY[src], hmax)
    blank = np.interp(w["h"].values, b["h"].values, b["co2c"].values)
    net = w["co2c"].values - blank
    return w["h"].values, net - net[0]


def net_table(mode: str = "hourly"):
    """Per-chamber termite number, net 24 h CO2 increment and per-termite rate."""
    N, net = [], []
    for k in TERMITE_KEYS:
        c0, c24 = endpoints(k, mode)
        b0, b24 = endpoints(BLANK_KEY[k[0]], mode)
        net.append((c24 - c0) - (b24 - b0))
        N.append(META[k]["N"])
    return np.array(N, float), np.array(net, float)


def blank_24h_changes(mode: str = "hourly") -> dict:
    """dCO2 of the three blanks, keyed by batch. Never averaged."""
    out = {}
    for src in C.BATCHES:
        c0, c24 = endpoints(BLANK_KEY[src], mode)
        out[C.BATCH_NAME[src]] = c24 - c0
    return out


def chamber_metrics() -> pd.DataFrame:
    """One row per series: the per-series metrics used by the figures."""
    rows = []
    for k in KEYS:
        m = META[k]
        w = win(k)
        c0, c24 = endpoints(k, "hourly")
        b0, b24 = endpoints(BLANK_KEY[m["src"]], "hourly")
        net = (c24 - c0) - (b24 - b0)
        rows.append(dict(
            key=f"{m['src']}-{m['sheet']}", src=m["src"], sheet=m["sheet"],
            N=m["N"], is_blank=m["is_blank"], n_records=m["n_records"],
            duration_h=m["duration_h"],
            temp_min=float(w.tmpc.min()), temp_max=float(w.tmpc.max()),
            hum_min=float(w.humc.min()), hum_max=float(w.humc.max()),
            hum_mean=float(w.humc.mean()), temp_mean=float(w.tmpc.mean()),
            hum_sat=float((w.humc >= 85).mean()),
            ch4_median=float(w.ch4c.median()), ch4_max=float(w.ch4c.max()),
            c0=c0, c24=c24, dco2=c24 - c0,
            net_dco2=net, rate_per_termite=net / m["N"] if m["N"] else np.nan,
            lin_r2=float(stats.linregress(w.h, w.co2c).rvalue ** 2),
            mono=float((hourly_bins(w).diff().dropna() > 0).mean()),
        ))
    return pd.DataFrame(rows)


def window_coverage() -> pd.DataFrame:
    """Records kept in the 0-24 h window and the resulting missing fraction.

    The nominal grid is one sample per minute, i.e. ``round(duration * 60) + 1``
    points over the window; the deficit is the fraction of minute points lost
    to polling dropouts. This reproduces the coverage columns of Table 4.
    """
    rows = []
    for k in KEYS:
        m = META[k]
        w = LONG[(LONG.src == k[0]) & (LONG.sheet == k[1]) & (LONG.h <= C.WINDOW_H)]
        dur = float(w["h"].max())
        nominal = int(round(dur * 60)) + 1
        rows.append(dict(
            key=f"{m['src']}-{m['sheet']}", src=m["src"],
            batch=C.BATCH_NAME[m["src"]], sheet=m["sheet"], N=m["N"],
            is_blank=m["is_blank"], records=len(w), duration_h=dur,
            start=w["timestr"].iloc[0], end=w["timestr"].iloc[-1],
            missing_pct=100.0 * (1 - len(w) / nominal),
        ))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- digest
def _digest() -> None:
    cov = window_coverage()
    print(f"dataset            : {LONG.shape[0]:,} minute-level records, "
          f"{len(KEYS)} series ({len(TERMITE_KEYS)} termite chambers + "
          f"{len(C.BATCHES)} blanks), 0-{C.WINDOW_H:g} h window")
    print("missing per batch  : "
          + ", ".join(f"{b} {v:.2f}%" for b, v in
                      cov.groupby("batch").missing_pct.mean().items()))
    m = chamber_metrics()
    t = m[~m.is_blank]
    print("blank 24 h dCO2    : "
          + ", ".join(f"{b} {C.half_up(v):+.1f} ppm"
                      for b, v in blank_24h_changes().items()))
    print(f"CO2 endpoints      : {m.c24.max():.0f} ppm max c24, "
          f"{m.c0.min():.0f} ppm min c0 (all 11 series)")
    print(f"within-series R^2  : {t.lin_r2.min():.3f}-{t.lin_r2.max():.3f} (raw CO2)")
    print(f"monotonic fraction : {t.mono.min():.2f}-{t.mono.max():.2f}")
    print(f"CH4 in window      : max {m.ch4_max.max():.0f} ppm")


if __name__ == "__main__":
    _digest()

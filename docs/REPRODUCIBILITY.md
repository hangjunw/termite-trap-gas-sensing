# Reproducibility report / 复现报告

Every table and figure in the paper is regenerated from
`data/termite_gas_measurements.csv` alone. This page records the command, the
verification result and the handful of places where a printed value differs in
the last digit from a naive recomputation.

---

## 1. How to run it

```bash
python -m pip install -r requirements.txt
python -m src.run_all
```

Outputs:

| Directory | Contents |
|---|---|
| `results/` | Tables 4–9 as CSV, `key_numbers.json`, `console_report.txt` |
| `figures/` | Figures 5–11 as 300 dpi PNG |

Individual stages:

```bash
python -m src.pipeline       # dataset digest only
python -m src.tables         # tables and statistics
python -m src.figures        # figures
```

---

## 2. The preprocessing chain

Applied identically to all eleven series (`src/pipeline.py`):

```
raw minute values
  → 7-point rolling median-absolute-deviation despiking (k = 6)
  → 10-minute median resampling
  → 0–24 h analysis window
  → c₀ = median of the first hourly bin, c₂₄ = value of the last hourly bin
  → ΔCO₂ = c₂₄ − c₀
  → net ΔCO₂ = ΔCO₂(chamber) − ΔCO₂(blank of the same batch)
```

Two conventions decide several table entries and are easy to get wrong:

1. **Within-series OLS R² (Table 5) is computed on the raw despiked CO₂ series**,
   not on the blank-corrected net curve. On the net curve the minimum is 0.982;
   the table's 0.990–0.999 comes from the raw series.
2. **Table 9 uses a different endpoint from Tables 5–7.** Table 9 grades the
   load from a *single final sample*, whereas Tables 5–7 use the hourly-bin
   endpoint. `pipeline.endpoints(key, mode)` switches between `"hourly"`,
   `"lasthour"` (the sensitivity check in §4.3) and `"sample"`.

---

## 3. Verification against the manuscript

| Manuscript item | Reproduced value | Match |
|---|---|---|
| Records (0–24 h window = the whole file) | 15,626 | ✅ |
| Missing per batch | 1.46 / 1.46 / 1.32 % | ✅ |
| Blank 24 h ΔCO₂ | +34.3 / −5.5 / +11.5 ppm | ✅ |
| Window CO₂ raw min / max (unsmoothed minute values) | 342 / 4,684 ppm | ✅ |
| Window CO₂ endpoint extremes (smoothed c₀ / c₂₄) | 404 / 4,676 ppm | ✅ |
| Within-series R² | 0.990–0.999 | ✅ |
| Monotonic fraction | 1.00 | ✅ |
| CH₄ max in window | 310 ppm | ✅ |
| **Table 4** records | 1,420 ×8, 1,422 ×3 | ✅ |
| **Table 5** c₀ / c₂₄ / ΔCO₂ / net / rate / R² | all 8 chambers | ✅ |
| **Table 5** blanks | +34.3 / −5.5 / +11.5 ppm | ✅ |
| **Table 6** T, RH, RH ≥ 85 %, CH₄ median/max | all 11 series | ✅ |
| **Table 7** slope | 6.75, SE 0.95, CI 4.41–9.08 | ✅ |
| **Table 7** R² / Pearson r | 0.893 / 0.945 | ✅ |
| **Table 7** Spearman ρ | 0.952 (p = 2.6 × 10⁻⁴) | ✅ |
| **Table 7** rate | 6.72 ± 0.90 ppm termite⁻¹ 24 h⁻¹, CV 13.4 % | ✅ |
| **Table 7** LOO Q² / mean abs. error | 0.80 / 16.4 % | ✅ |
| **Table 7** last-full-hour endpoint | 6.65 / 0.896; Δ 26.5 ppm (max 47.5) | ✅ |
| **Table 7** Batch 2 only | 7.47 / 0.964, p = 0.003 | ✅ |
| **Table 7** cross-batch transfer | −11.9 to −21.4 % | ✅ |
| **Table 7** ANCOVA batch F(2,4) | 2.45, p = 0.20, R² = 0.952, slope 7.24 | ✅ |
| **Table 8** five noise tiers (σ, LOD, LOQ) | 6.4/3.1/9.5, 17.0/8.3/25.2, 19.9/9.8/29.6, 329.5/161.2/488.4, 264.0/116.6/353.3 | ✅ |
| **Table 9** six durations | R², p, LOO MAE, worst case, SD | ✅ |
| §4.2 kinetics | exp. preferred 2/8 (τ = 27.3 / 26.4 h); line preferred 6/8 (ΔAIC +5.9 to +96); final-4-h slope 0.78–0.85 | ✅ |
| §4.4 CH₄ selectivity | zero-order +0.328 / +0.592 / −0.095; partial −0.045 / +0.554 / −0.211; n = 1,015 | ✅ |
| §5.4 batch variance components | between 227 ppm, within 261 ppm, ICC 0.43 | ✅ |
| Time to alarm (3 × SD of the blanks) | 10–87 min, threshold 59.8 ppm | ✅ |

Run `src/tables.py` and compare `results/console_report.txt` line by line.

---

## 4. Known last-digit differences

These are rounding artefacts, not analysis differences. Both are documented in
the code.

1. **Half-up vs half-to-even rounding.** The manuscript's numbers were formatted
   by a spreadsheet, which rounds exact halves away from zero; Python's
   `round` rounds them to even. The Batch 1 blank changes by **34.25 ppm**,
   which reads **+34.3** in Table 5 and **+34.2** under `round`. The released
   code formats through `config.half_up` so the tables read as printed.
2. **LOD/LOQ are computed from unrounded σ.** Table 8 prints σ to one decimal,
   but the LOD/LOQ columns divide the *unrounded* σ. Rounding σ first moves the
   pooled row's LOQ to 488.2 instead of the printed 488.4, and the Batch-2 row's
   to 353.2 instead of 353.3.
3. **The 24 h boundary of the despiker.** The despiker is a *centred* 7-point
   rolling MAD, so the last sample of each series is smoothed together with its
   neighbours. The released file stops at `h = 24`, which means the final 10-min
   bin of every series is cleaned with a truncated window — one bin per series,
   changed by at most 9.5 ppm. Only c₂₄ and the quantities derived from it are
   affected (Table 5 endpoints, the pooled slope, Table 8's blank-to-blank tier,
   Table 9's 24 h row, the alarm threshold); everything earlier in the window is
   bit-identical. The values reproduced here are the ones obtained from the
   released file. The post-24 h records that the paper's original reduction used
   for that boundary are available on request.

If you recompute these values with your own formatting and get 34.2, 488.2 or
353.2, your arithmetic is right and the difference is only in the formatting
chain or in where the window is cut.

---

## 5. What is *not* in this repository

| Item | Where it is |
|---|---|
| Calibration sweep, coefficients and fitting script | on request — see `calibration/README.md` |
| Firmware and hardware design files for the sensor nodes | not released |
| The raw 1 Hz logging files of the batches | reduced to the released 1-min series; a fuller export, including the post-24 h tail of every chamber, is available on request |

The `Data Availability Statement` in the paper matches this arrangement.

---

## 6. Environment

Tested with:

| Package | Version |
|---|---|
| Python | 3.13 |
| numpy | 2.4 |
| pandas | 3.0 |
| scipy | 1.18 |
| matplotlib | 3.11 |

The analysis uses only numpy / pandas / scipy; `matplotlib` is needed for the
figures. Nothing beyond the standard library is required to *parse* the released
CSV. The mixed model in `tables._reml_batch_model` is a small self-contained
REML implementation, so no mixed-model package is required.

# A Networked Multi-Gas Sensing System for In-Trap Monitor-ing of Termite-Associated CO₂ and CH₄: Design and Evaluation

We built a networked system that records CO₂ (NDIR), a metal-oxide CH₄ channel, temperature and humidity inside sealed traps, polled over RS-485/Modbus by one host.

The CSV (`termite_gas_measurements.csv`) is the **only** data file released. It is plain text so that GitHub can
diff it and so that Excel, R, MATLAB or Python can open it without a reader.

---


## 1. `termite_gas_measurements.csv`

**Shape**: one header row + **15,626 data rows × 6 columns**.
File size ≈ 0.72 MB, encoded **UTF-8 with BOM** (so Excel on a Chinese Windows
locale shows the headers correctly), line endings LF.

This file contains the complete 0–24 h dataset used in the paper: minute-level traces from all chambers. No data exists outside this window. The CO₂ range (342–4,684 ppm) and CH₄ range (0–310 ppm) reported in the paper are derived from this file alone.

```
CO2 (ppm),Temperature (°C),Relative humidity (%RH),CH4 (ppm),Timestamp,Chamber (N)
531,21.54,61.56,0,08-24 12:46,Batch 1 · Blank (0)
534,21.46,61.13,0,08-24 12:47,Batch 1 · Blank (0)
...
965,24.00,75.76,0,08-24 12:46,Batch 1 · 310
...
```

### Columns

The names are English and follow the manuscript's own wording: `CO2`,
`Temperature` and `Relative humidity` as in Table 1, and `Chamber (N)` as in
Table 5.

| # | Column | Type | Unit | Meaning |
|---|---|---|---|---|
| 1 | `CO2 (ppm)` | int | ppm | **CO₂ concentration** — the primary response variable |
| 2 | `Temperature (°C)` | float | °C | chamber temperature |
| 3 | `Relative humidity (%RH)` | float | %RH | relative humidity (used by the sealed-chamber / survival criterion) |
| 4 | `CH4 (ppm)` | int | ppm | **CH₄ channel reading** from the MOx module — see caveat 7 |
| 5 | `Timestamp` | str | `MM-DD HH:MM` | acquisition time; **no year** (see caveat 4) |
| 6 | `Chamber (N)` | str | — | which chamber the row belongs to; **`N` is the termite number** |

### The `Chamber (N)` column

The Chamber (N) column follows the format Batch number · value. Each value represents a single chamber measurement within that batch. Blanks are recorded as Batch number · Blank (0).

| Value | Batch | `N` | blank? |
|---|---|---|---|
| `Batch 1 · 310` | 1 | 310 | no |
| `Batch 1 · Blank (0)` | 1 | 0 | **yes** |
| `Batch 2 · 105` … `Batch 2 · 500` | 2 | 105 … 500 | no |
| `Batch 3 · 343`, `Batch 3 · 461` | 3 | 343, 461 | no |

- `N = 0` (written `Blank (0)`, as in Table 4's *Condition (N)*) marks a blank
  control — there were three of them, one per batch.
- The dose axis *x* is the termite number **N** (105 … 500).

### Rows

- **Every row lies inside the analysis window.** Each chamber contributes its
  first 24 h, `h ≤ 24`: **1,420 rows** for Batches 1–2 and **1,422** for Batch 3
  (1,420 × 8 + 1,422 × 3 = **15,626**). Nothing beyond 24 h is included, so the
  row count and the paper's window are the same object.
- One row per sample, in **acquisition order**, grouped by chamber.
- All chambers of a batch share one elapsed-time axis; **the three batches do not
  overlap in time** and their time axes must never be aligned.
- Elapsed hours are not a column: `h = (t − t₀)/3600`, where `t₀` is the first
  sample of the same `Chamber (N)`; it therefore runs from 0 to 24.

### Loading it

pandas.read_csv() loads the file without any special arguments. No rows need to be skipped.

```python
import pandas as pd

df = pd.read_csv("termite_gas_measurements.csv", encoding="utf-8-sig")

# split "Batch 1 · 310" into the batch and the condition, and recover N
parts = df["Chamber (N)"].str.partition(" \u00b7 ")
df["batch"], df["condition"] = parts[0].str.strip(), parts[2].str.strip()
df["N"] = pd.to_numeric(
    df["condition"].where(df["condition"] != "Blank (0)", "0"))
df["is_blank"] = df["N"] == 0

# timestamps have no year: assume one, then measure elapsed hours per chamber.
# `% 86400` undoes the midnight rollover, where the parsed time steps back ~24 h.
df["t"] = pd.to_datetime("2025-" + df["Timestamp"], format="%Y-%m-%d %H:%M")
df["h"] = (df.groupby("Chamber (N)", sort=False)["t"]
             .transform(lambda t: (t.diff().dt.total_seconds().fillna(0)
                                   % 86400).cumsum() / 3600))
```


### The 11 chambers

Every chamber contributes the same **24.0 h** window, so the only things that
vary between them are where that window falls and how large the readings get.

| `Chamber (N)` | N | blank | rows | from → to | CO₂ range (ppm) | CH₄ range (ppm) |
|---|---|---|---|---|---|---|
| Batch 1 · Blank (0) | 0 | ✔ | 1,420 | 08-24 12:46 → 08-25 12:46 | 352 – 534 | 0 – 0 |
| Batch 1 · 310 | 310 | | 1,420 | 08-24 12:46 → 08-25 12:46 | 965 – 2,878 | 0 – 104 |
| Batch 2 · Blank (0) | 0 | ✔ | 1,420 | 08-28 15:18 → 08-29 15:18 | 351 – 735 | 0 – 0 |
| Batch 2 · 105 | 105 | | 1,420 | 08-28 15:18 → 08-29 15:18 | 458 – 1,310 | 0 – 0 |
| Batch 2 · 207 | 207 | | 1,420 | 08-28 15:18 → 08-29 15:18 | 952 – 2,196 | 0 – 12 |
| Batch 2 · 324 | 324 | | 1,420 | 08-28 15:18 → 08-29 15:18 | 805 – 3,429 | 0 – 106 |
| Batch 2 · 412 | 412 | | 1,420 | 08-28 15:18 → 08-29 15:18 | 592 – 3,382 | 0 – 310 |
| Batch 2 · 500 | 500 | | 1,420 | 08-28 15:18 → 08-29 15:18 | 872 – 4,684 | 0 – 238 |
| Batch 3 · Blank (0) | 0 | ✔ | 1,422 | 09-04 12:22 → 09-05 12:22 | 342 – 620 | 0 – 0 |
| Batch 3 · 461 | 461 | | 1,422 | 09-04 12:22 → 09-05 12:22 | 706 – 3,419 | 0 – 219 |
| Batch 3 · 343 | 343 | | 1,422 | 09-04 12:22 → 09-05 12:22 | 699 – 2,939 | 0 – 150 |

Whole-file extremes: CO₂ **342 – 4,684 ppm**, CH₄ **0 – 310 ppm**,
temperature **20.0 – 32.1 °C**, relative humidity **48.9 – 94.6 %RH** — exactly
the ranges the manuscript quotes.

---

## 2. Caveats (please read before reusing the data)

Sampling interval.​ Nominal resolution is 1 minute, but roughly 1.3–1.5 %​ of the minute marks are missing in every chamber due to polling dropouts. Row count therefore does not equal elapsed minutes. Resample or interpolate against h before differentiating.
The file ends at 24 h by design.​ Every chamber stops at h = 24. There is no data beyond this window to trim. The actual acquisition ran longer (48.4–51.8 h per chamber), but after 24 h the termites may be stressed or dead. Those records fall outside the paper's scope and are not included here. The 24 h window is the complete dataset for this study.
Values are raw and not despiked.​ All extremes fall within reasonable ranges (CO₂ 342–4,684 ppm, CH₄ 0–310 ppm, T 20.0–32.1 °C, RH 48.9–94.6 %RH).
Blanks must be paired by batch.​ Net accumulation is calculated as ΔCO₂(chamber) − ΔCO₂(blank from the same batch). The three blanks are not interchangeable and should never be merged or averaged. Their 24 h drifts are +34.3, −5.5, and +11.5 ppm — they differ in sign.
Batch effects exist.​ Batches 1 and 3 read 11.9–21.4 % below the Batch 2 model prediction. Treat batch as a random or fixed effect, or report within-batch and between-batch results separately.
The CH₄ channel is a MOx reading, not a flux.​ It depends strongly on temperature (partial r = 0.55 within chambers). The blanks are both dry and CH₄-free, so humidity and termite presence are fully confounded. Only the ranking​ of chambers is supported by these data.


1. **Sampling interval.** Nominal resolution is 1 minute, but roughly 1.3–1.5 %​ of the minute marks are missing in every chamber due to polling dropouts. Row count therefore does not equal elapsed minutes. Resample or interpolate against h before differentiating.
2. **The file ends at 24 h by design.** Every chamber stops at 'h = 24'. There is no data beyond this window to trim. The actual acquisition ran longer (48.4–51.8 h per chamber), but after 24 h the termites may be stressed or dead. Those records fall outside the paper's scope and are not included here. The 24 h window is the complete dataset for this study.
3. **Values are raw and not despiked.** All extremes fall within reasonable ranges (CO₂ 342–4,684 ppm, CH₄ 0–310 ppm, T 20.0–32.1 °C, RH 48.9–94.6 %RH).
4. **Blanks must be paired by batch.** Net accumulation is calculated as ΔCO₂(chamber) − ΔCO₂(blank from the same batch). The three blanks are not interchangeable and should never be merged or averaged. Their 24 h drifts are +34.3, −5.5, and +11.5 ppm — they differ in sign.
5. **Batch effects exist.** Batches 1 and 3 read 11.9–21.4 % below the Batch 2 model prediction. Treat batch as a random or fixed effect, or report within-batch and between-batch results separately.
6. **The CH₄ channel is a MOx reading, not a flux.** It depends strongly on temperature (partial r = 0.55 within chambers). The blanks are both dry and CH₄-free, so humidity and termite presence are fully confounded. Only the ranking​ of chambers is supported by these data.

---



## 3. Licence

Released under **CC BY 4.0** — 
Please cite the paper if you use these data.

Citation：If this project is useful for your research, please cite this work after the paper is formally published.
Corresponding author: whj@zafu.edu.cn

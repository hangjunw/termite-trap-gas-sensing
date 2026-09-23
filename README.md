# Termite trap gas sensing — code and data

Reproduction package for

> **A Networked Multi-Gas Sensing System for In-Trap Monitoring of Termite-Associated CO₂ and CH₄: Design and Evaluation**
> Hangjun Wang, Hao Huang, Shan Wu, et al.

A networked sensor node measures CO₂ (NDIR), CH₄ (MOx) and temperature/humidity
inside sealed termite chambers holding 105–500 workers. This repository holds the
measurements, the analysis code that regenerates every table and figure in the
paper, and the documentation needed to reuse the data.

---

## Quick start

```bash
git clone https://github.com/hangjunw/termite-trap-gas-sensing
cd termite-trap-gas-sensing
python -m pip install -r requirements.txt
python -m src.run_all
```

`run_all` prints a dataset digest, recomputes Tables 4–9 and regenerates
Figures 5–11. It reads `data/termite_gas_measurements.csv` directly — there is
no data-preparation step.

---

## What is here

```
├── data/
│   ├── termite_gas_measurements.csv   the measurements
│   │                                  15,626 rows / 11 chambers / 6 columns
│   └── README.md                      data documentation (English)
├── src/
│   ├── config.py                paths, constants, colour palette
│   ├── pipeline.py              CSV parsing + despiking / resampling / endpoints
│   ├── tables.py                Tables 4-9 + all in-text statistics
│   ├── figures.py               Figures 5-11
│   └── run_all.py               one-command driver
├── results/                     generated: tables, model_comparison.csv, key_numbers.json, console_report.txt
└── figures/                     generated: Figures 5-11 (300 dpi PNG)
```

The data file is one flat table — a single header row and one row per sample —
with the chamber carried in a column rather than in block separators:

```
CO2 (ppm),Temperature (°C),Relative humidity (%RH),CH4 (ppm),Timestamp,Chamber (N)
531,21.54,61.56,0,08-24 12:46,Batch 1 · Blank (0)
965,24.00,75.76,0,08-24 12:46,Batch 1 · 310
```

Column names are English and follow the manuscript's own wording (`Chamber (N)`
as in Table 5, whose `Batch 1 · 310` labels are reproduced verbatim).
`src/pipeline.py::load_long()` splits the label into batch, condition and termite
number, and builds the elapsed-hours axis. See `data/README.md` for the field
list and a standalone loader.

---

## The experiment in one paragraph

Eleven sealed chambers were run across three independent batches: eight loaded
with 105–500 *Coptotermes formosanus* workers plus one blank control per batch.
Each chamber held a single wood block and no soil. Every node logged CO₂, CH₄,
temperature and relative humidity once per minute. The released data and the
paper both use the **first 24 h** (the 0–24 h analysis window). Because termites
respire CO₂, the accumulation inside a
sealed chamber should scale with the number of workers — which is what the
dose–response below tests.

---

## Analysis chain

Applied identically to all eleven series:

```
raw minute values
  → 7-point rolling MAD despiking (k = 6)
  → 10-minute median resampling
  → 0–24 h window
  → c₀ = first hourly-bin median, c₂₄ = last hourly-bin value
  → ΔCO₂ = c₂₄ − c₀
  → net ΔCO₂ = ΔCO₂(chamber) − ΔCO₂(blank of the same batch)
```

### Headline results

| Quantity | Value |
|---|---|
| Records in the 0–24 h window | **15,626** (the whole released file) |
| Dose–response slope | **6.75 ± 0.95** ppm termite⁻¹ 24 h⁻¹ |
| R² / Spearman ρ | 0.893 / 0.952 |
| Leave-one-out Q² | 0.80 (mean abs. error 16.4 %) |
| Per-termite rate | 6.72 ± 0.90 ppm termite⁻¹ 24 h⁻¹ (CV 13.4 %) |
| Batch variance components | 227 ppm between, 261 ppm within (ICC 0.43) |
| Blank-to-blank 24 h drift | +34.3 / −5.5 / +11.5 ppm (reported separately) |
| LOO grading error at 1 h / 24 h | 70.3 % / 16.0 % |

Full verification table: `docs/REPRODUCIBILITY.md`.

---

## Three rules the code enforces

1. **The 0–24 h window only.** The acquisition ran for 48–52 h, but the released
   file and every reported statistic stop at 24 h. Beyond that the termites may
   be stressed or dead.
2. **The three blanks are never merged.** Net accumulation always subtracts the
   blank of the *same batch*. The three blanks drift in different directions
   (+34.3, −5.5, +11.5 ppm), so averaging them would be meaningless.
3. **Elapsed hours only, never calendar dates.** The source timestamps carry no
   year; any year shown for the released `Timestamp` column is a parsing
   artefact, not data.

---

## Reproducing a single item

```bash
python -m src.pipeline       # dataset digest
python -m src.tables         # results/table4..9*.csv, key_numbers.json
python -m src.figures        # figures/fig5..11*.png
```

In a notebook:

```python
from src import pipeline, tables

x, y = tables._dose_xy()                       # termite number vs net ΔCO₂
print(tables.table7_statistics()["slope"])     # 6.749...
h, net = pipeline.net_series(("data7", "500")) # blank-corrected curve, N = 500
```

---

## Data and calibration availability

* **Data** — released in this repository under CC BY 4.0.
* **Calibration** — the 24-min decoupled sweep, the fitted coefficients, the
  fitting script and the steady-state points are available **from the
  corresponding author on reasonable request**; `calibration/README.md` states
  exactly what the package contains and how to ask for it.

---

## Licence and citation

Code: MIT (`LICENSE`). Data: CC BY 4.0. See `CITATION.cff`.

Corresponding author: whj@zafu.edu.cn

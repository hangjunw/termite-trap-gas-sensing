from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"

MEASUREMENTS_CSV = DATA / "termite_gas_measurements.csv"

RESULTS.mkdir(exist_ok=True)
FIGURES.mkdir(exist_ok=True)

# --- the released data file's layout -------------------------------------
# The measurements are one flat table: a single header row, then one row per
# sample.  Which chamber a row belongs to is carried by a column instead of by
# block separators, because a CSV cannot hold worksheets.
#
# Column names are English and follow the manuscript's own wording: CO2 /
# Temperature / Relative humidity / CH4 come from Table 1, and "Chamber (N)"
# from Table 5.
HEADER = ["CO2 (ppm)", "Temperature (°C)", "Relative humidity (%RH)",
          "CH4 (ppm)", "Timestamp", "Chamber (N)"]
# Maps the released headers onto the short names used throughout the code.
FIELDS = {"CO2 (ppm)": "co2", "Temperature (°C)": "temp",
          "Relative humidity (%RH)": "hum", "CH4 (ppm)": "ch4",
          "Timestamp": "timestr"}
CHAMBER_COL = "Chamber (N)"
# Chamber labels reproduce Table 5 verbatim, e.g. "Batch 1 · 310".  The
# separator is U+00B7 MIDDLE DOT with one space either side.
CHAMBER_SEP = " \u00b7 "
# The blank control (no termites) is labelled as in Table 4's Condition (N).
BLANK_CONDITION = "Blank (0)"
# The timestamps carry month, day and time but no year; this is the year used
# to parse them.  Only relative durations are ever reported.
YEAR_ASSUMED = 2025

# --- batch identity -------------------------------------------------------
# The three batches were acquired on different dates with different colonies;
# they must never be time-aligned across batches (see data/README.md).
BATCHES = ["data1", "data2", "data3"]
BATCH_NAME = {"data1": "Batch 1", "data2": "Batch 2", "data3": "Batch 3"}
SRC_OF_BATCH = {v: k for k, v in BATCH_NAME.items()}
BATCH_DATES = {"data1": "24-26 Aug", "data2": "28-30 Aug", "data3": "4-6 Sep"}


def chamber_label(src: str, condition: str) -> str:
    """Chamber label in the manuscript's Table 5 notation, e.g. ``Batch 1 · 310``."""
    return f"{BATCH_NAME[src]}{CHAMBER_SEP}{condition}"


def condition_of(src: str, N: int) -> str:
    """The ``Condition (N)`` text used in the released ``Chamber (N)`` column."""
    return BLANK_CONDITION if N == 0 else str(int(N))


# Colour-blind-safe palette (Okabe-Ito) used in every figure.
BATCH_COLOR = {"data6": "#0072B2", "data7": "#D55E00", "data9": "#009E73"}
BLANK_COLOR = "#333333"
ACCENT = "#D55E00"
BLUE = "#0072B2"
SKY = "#56B4E9"
GREY = "#888888"

# --- analysis choices fixed in the manuscript ----------------------------
WINDOW_H = 24.0          # analysis window, hours
DESPIKE_WIN = 7          # rolling window for the MAD despiker
DESPIKE_K = 6.0          # MAD multiplier
RESAMPLE = "10min"       # resampling grid

# Mole volume used for the mass-specific rate conversion (chamber temperature).
MOLAR_VOLUME_STP = 22.414        # L/mol at 0 degC, 101.325 kPa (not used for the paper's value)
WORKER_MASS_MG = 2.3             # mean worker fresh mass measured in this study
CHAMBER_VOLUME_L = 7.5           # nominal chamber volume


def half_up(value: float, nd: int = 1) -> float:
    """Round half away from zero.

    The manuscript's values were formatted by a spreadsheet, which rounds
    halves up, whereas Python's built-in ``round`` is half-to-even.  The two
    differ only on exact halves: the Batch 1 blank changes by 34.25 ppm, which
    reads +34.3 in Table 5 but +34.2 under ``round``.  Formatting through this
    helper keeps the released tables identical to the paper.
    """
    from decimal import Decimal, ROUND_HALF_UP
    return float(Decimal(str(value)).quantize(Decimal(1).scaleb(-nd),
                                              rounding=ROUND_HALF_UP))

# -*- coding: utf-8 -*-
"""Run the whole reproduction pipeline in one command.

    python -m src.run_all

Steps
-----
1. sanity-check the measurements file and print a digest of the headline numbers
2. recompute Tables 4-9 and every in-text statistic -> ``results/``
3. regenerate Figures 5-11                          -> ``figures/``

Everything is derived from ``data/termite_gas_measurements.csv`` alone; no
intermediate file from the original project is required.
"""
from __future__ import annotations

import sys
from pathlib import Path

# allow `python src/run_all.py` as well as `python -m src.run_all`
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import config as C                       # noqa: E402
from src import pipeline, tables, figures         # noqa: E402


def main() -> None:
    print("=" * 72)
    print("Termite trap gas sensing -- full reproduction")
    print(f"repository root : {C.ROOT}")
    print(f"measurements    : {C.MEASUREMENTS_CSV.name}")
    print("=" * 72)

    print("\n[1/3] dataset digest")
    print("-" * 72)
    pipeline._digest()

    print("\n[2/3] recomputing tables and statistics")
    print("-" * 72)
    tables.main()

    print("\n[3/3] regenerating figures")
    print("-" * 72)
    figures.main()

    print("\n" + "=" * 72)
    print("done.  outputs:")
    print(f"  tables  -> {C.RESULTS.relative_to(C.ROOT)}/")
    print(f"  figures -> {C.FIGURES.relative_to(C.ROOT)}/")
    print("=" * 72)


if __name__ == "__main__":
    main()

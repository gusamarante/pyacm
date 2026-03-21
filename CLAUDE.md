# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

pyacm is a Python implementation of the ACM (Adrian, Crump, Moench) Term Premium model from "Pricing the Term Structure with Linear Regressions" (2013). It decomposes yield curves into risk-neutral yields and term premia using a three-step linear regression approach.

## Install & Run

```bash
pip install -e .
# Run the US example
python example_us.py
```

Dependencies: matplotlib, numpy, pandas, scikit-learn, statsmodels (declared in `setup.py`).

No test suite exists. There are no linting or formatting configurations.

## Architecture

The entire model lives in a single class: `NominalACM` in `pyacm/acm.py`. The constructor runs the full estimation pipeline:

1. **Data prep** — resamples curve to monthly, computes PCA factors (skipping first 2 maturities), computes excess returns
2. **Step 1** — VAR(1) on monthly principal components (`_estimate_var`)
3. **Step 2** — Excess return regression on lagged factors + VAR residuals (`_excess_return_regression`)
4. **Step 3** — Convexity-adjusted price of risk extraction (`_retrieve_lambda`)
5. **Derived outputs** — short rate equation, affine yield coefficients, model-implied yields, risk-neutral yields, term premium, expected returns

All estimation uses monthly-frequency data. Daily/higher-frequency outputs are produced by projecting daily data through the monthly-estimated factor loadings.

## Key Input Requirements

- `curve`: DataFrame of annualized log-yields for zero-coupon bonds
- Columns must be consecutive integers starting from 1 (monthly maturities)
- Index must be a DatetimeIndex
- `selected_maturities` controls which maturities enter the regression (important for liquidity filtering)
- Optional `curve_m` allows passing a separate monthly curve for estimation

## Key Attributes on `NominalACM`

- `tp` — term premium estimates (the main output)
- `miy` — model-implied/fitted yields
- `rny` — risk-neutral yields
- `fwd_curve(date)` — computes forward curves (observed, fitted, risk-neutral) for a given date
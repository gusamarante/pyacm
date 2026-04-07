# SR570 Data Sources for Replication

## Overview

This document catalogs every data series used in Abrahams, Adrian, Crump, and Moench (2013), "Decomposing Real and Nominal Yield Curves" (NY Fed Staff Report No. 570), with download sources. The paper's estimation uses end-of-month observations from **1999:01 to 2014:11** (T = 191). We extend the sample to the present and expand the cross-section of maturities where possible.

---

## 1. U.S. Nominal Zero-Coupon Treasury Yields

**Paper usage:** Cross-section of nominal yields used to extract K_N = 3 principal components. Maturities n = 3, 6, 12, 24, ..., 120 months. Also used to compute N_N = 11 one-month holding period excess returns at maturities n = 6, 12, 24, ..., 120 months. The 1-month yield serves as the nominal risk-free rate.

**Source:** Gürkaynak, Sack, and Wright (2007) — "The U.S. Treasury Yield Curve: 1961 to the Present."

**Direct download:**
- **Landing page:** https://www.federalreserve.gov/data/nominal-yield-curve.htm
- **CSV file:** https://www.federalreserve.gov/data/yield-curve-tables/feds200628.csv

**Details:** Daily frequency, 1961–present. Updated weekly (typically Tuesday for data through the prior Friday). Provides Svensson parameters (BETA0–BETA3, TAU1, TAU2) from which zero-coupon yields at any maturity can be computed. Also provides pre-computed zero-coupon yields, par yields, and forward rates at selected maturities.

**Cross-section expansion:** The paper uses maturities 3–120 months. The GSW dataset publishes yields starting from maturities as short as 1 year. Using the Svensson parameters, you can evaluate the curve at any maturity. Consider extending up to 360 months (30 years) for the nominal curve, as long-maturity nominal Treasuries are liquid and have been issued consistently.

**FRED mirror (for programmatic access):**
- Selected maturities are available as individual FRED series, e.g.:
  - 1-year: `SVENY01` 
  - 5-year: `SVENY05`
  - 10-year: `SVENY10`
  - etc.

---

## 2. U.S. TIPS (Real) Zero-Coupon Yields

**Paper usage:** Cross-section of TIPS yields used to extract K_R = 2 orthogonalized real principal components. Maturities n = 24, ..., 120 months. N_R = 9 excess returns on TIPS at the same maturities. Also used to estimate the inflation parameters π₀ and π₁.

**Source:** Gürkaynak, Sack, and Wright (2010) — "The TIPS Yield Curve and Inflation Compensation."

**Direct download:**
- **Landing page:** https://www.federalreserve.gov/data/tips-yield-curve-and-inflation-compensation.htm
- **CSV file:** https://www.federalreserve.gov/data/yield-curve-tables/feds200805.csv

**Details:** Daily frequency, 1999:01–present. Updated weekly. Provides Svensson parameters for the TIPS curve, plus pre-computed real zero-coupon yields and inflation compensation measures at selected maturities. TIPS maturities below 24 months are not published because the CPI indexation lag distorts short-maturity TIPS pricing.

**Cross-section expansion:** The paper uses 24–120 months. Since the 20-year TIPS was reintroduced in 2004 and 30-year TIPS have been issued periodically, you can extend TIPS yields up to 240 months (20 years) or even 360 months (30 years) for recent sample periods, again by evaluating the Svensson parameters at longer maturities. Be cautious at maturities beyond the longest outstanding TIPS, as the curve is extrapolated.

**Key fields in the CSV:**
- `TIPS_YieldCurve_*` — real zero-coupon yields
- `TIPS_FittingError_RMSE` — root-mean-square fitting error (used for liquidity proxy)
- Svensson parameters: `BETA0`, `BETA1`, `BETA2`, `BETA3`, `TAU1`, `TAU2`

---

## 3. TIPS Yield Curve Fitting Errors (Liquidity Proxy #1)

**Paper usage:** Average absolute TIPS yield curve fitting error from the Nelson-Siegel-Svensson model. This is the first of two components of the composite liquidity indicator. Large fitting errors proxy for market stress and poor relative liquidity of TIPS.

**Source:** Same GSW (2010) dataset as above.

**Direct download:** Same CSV as Series 2 above.

**Construction note:** The paper uses the average absolute fitting error. The CSV file provides fitting error statistics. You may need to compute the average absolute fitting error across the TIPS maturities used in the NSS estimation for each day. Alternatively, the published RMSE can serve as a close proxy.

---

## 4. Primary Dealer Transaction Volumes — Treasury vs. TIPS (Liquidity Proxy #2)

**Paper usage:** 13-week moving average of the ratio of primary dealers' nominal Treasury transaction volumes to TIPS transaction volumes. This is the second component of the composite liquidity indicator.

**Source:** Federal Reserve Bank of New York, FR2004 "Weekly Release of Primary Dealer Positions, Transactions, and Financing."

**Direct download:**
- **Interactive data tool:** https://www.newyorkfed.org/markets/counterparties/primary-dealers-statistics
- **Bulk export:** From the above page, use "Export data to: CSV" link for the weekly release.
- Data available from January 28, 1998 to present, updated weekly (Thursdays).

**Construction notes:**
- From the FR2004B data (cumulative weekly transactions), extract:
  - Total nominal Treasury transactions (Bills + Coupons, all maturities)
  - TIPS transactions
- Compute ratio: Nominal Treasury volume / TIPS volume
- Apply 13-week backward-looking moving average

**Important caveat:** The FR2004 reporting structure changed on January 5, 2022 (more granular breakdowns). Ensure consistency across the structural break. Older data and newer data may require slightly different field mappings.

---

## 5. Consumer Price Index — CPI-U, Not Seasonally Adjusted

**Paper usage:** The price index Q_t used to calculate TIPS payouts. Seasonally unadjusted CPI-U (All Urban Consumers, All Items).

**Source:** U.S. Bureau of Labor Statistics (BLS).

**Direct download (FRED):**
- **Series ID:** `CPIAUCNS`
- **URL:** https://fred.stlouisfed.org/series/CPIAUCNS
- Monthly, Not Seasonally Adjusted, 1913–present.

**Direct download (BLS):**
- https://data.bls.gov/timeseries/CUUR0000SA0

**FRED API:**
```
https://api.stlouisfed.org/fred/series/observations?series_id=CPIAUCNS&api_key=YOUR_KEY&file_type=json
```

---

## 6. Composite Liquidity Indicator — Construction

**Paper usage:** The sixth pricing factor in the model. Constructed as:

1. Standardize Series 3 (TIPS fitting errors) and Series 4 (volume ratio, 13-week MA)
2. Compute their equal-weighted average
3. Shift the index so its minimum is zero (add the negative of the time-series minimum)

This ensures the liquidity factor is non-negative, so illiquidity can only raise yields.

**No separate download needed** — derived from Series 3 and 4 above.

---

## Summary Table

| # | Series | Frequency | Source | Access | Format |
|---|--------|-----------|--------|--------|--------|
| 1 | Nominal zero-coupon yields (GSW 2007) | Daily | Federal Reserve Board | Public | CSV |
| 2 | TIPS zero-coupon yields (GSW 2010) | Daily | Federal Reserve Board | Public | CSV |
| 3 | TIPS NSS fitting errors | Daily | Federal Reserve Board (same as #2) | Public | CSV |
| 4 | Primary dealer Treasury/TIPS volumes | Weekly | NY Fed (FR2004) | Public | CSV/Excel |
| 5 | CPI-U (NSA) | Monthly | BLS / FRED | Public | CSV/API |
| 6 | Composite liquidity indicator | — | Derived from #3 and #4 | — | — |

---

## Notes on Cross-Section and Time-Series Expansion

**Time series:** The paper sample runs 1999:01–2014:11. All public series (1–5, 7–8, 11, 13–14) continue to be updated and can be extended to the present. The binding constraint on the start date is the TIPS curve (available from 1999:01).

**Cross-section (nominal):** The paper uses n = 3, 6, 12, 24, ..., 120 months for PCA and n = 6, 12, 24, ..., 120 months for excess returns. Since the GSW nominal curve is well-identified out to 30 years, you can add maturities at 132, 144, ..., 360 months.

**Cross-section (TIPS):** The paper uses n = 24, ..., 120 months. With 20-year and 30-year TIPS now regularly issued, you can extend to 132, 144, ..., 240 or 360 months, though care is needed at the very long end where the Svensson extrapolation may be less reliable.

**Cross-section (U.K.):** The paper uses nominal n = 6, 12, ..., 120 months and real n = 60, ..., 120 months. The Bank of England publishes nominal yields up to 40 years and real yields where available. Consider extending both.
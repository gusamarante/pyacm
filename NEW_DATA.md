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

## 7. U.K. Nominal and Real Zero-Coupon Gilt Yields (Robustness Application)

**Paper usage:** Section 5.5 estimates the model on U.K. data. End-of-month zero-coupon yields from 1985:01 to 2012:12 (T = 336). Nominal: n = 6, 12, 24, ..., 120 months (N = 11 maturities). Real: n = 60, 66, ..., 120 months (N_R = 8 maturities). The 1-month nominal yield serves as the short rate. No liquidity factor in the U.K. specification.

**Source:** Bank of England yield curve estimates (Anderson and Sleath, 2001).

**Direct download:**
- **Landing page:** https://www.bankofengland.co.uk/statistics/yield-curves
- Spreadsheets are downloadable directly from the landing page (nominal spot, real spot, forward rates).
- Nominal curves available daily from 1979:01:02. Real curves from 1985:01:02.

**Details:** Yields are continuously compounded and quoted on an annual basis. The Bank provides spot rates and instantaneous forward rates. Monthly intervals up to 5 years, semi-annual intervals for longer maturities.

**Cross-section expansion:** The Bank publishes nominal yields up to 40 years and real yields up to ~25 years (limited by outstanding index-linked gilts). You could expand the real maturities beyond 120 months and push the nominal maturities beyond 120 months as well.

---

## 8. U.K. Retail Price Index (RPI)

**Paper usage:** The U.K. analog of CPI-U. Used as Q_t for inflation-indexed gilt payoffs.

**Source:** U.K. Office for National Statistics (ONS).

**Direct download:**
- **ONS series CHAW (Jan 1987 = 100):** https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/chaw/mm23
- **DMO (longer history, from June 1980):** https://www.dmo.gov.uk/data/ExportReport?reportCode=D4O
- Monthly frequency.

---

## Additional Series Used in the Analysis (Not for Core Estimation)

The following series appear in the paper's empirical analysis of the inflation risk premium (Section 5.1) and other applications. They are not used in the core model estimation but are useful for replication of the full set of results.

### 9. SMOVE — Swaption Implied Treasury Volatility

**Paper usage:** 3-month swaption implied Treasury volatility (from Merrill Lynch). Correlated with the estimated inflation risk premium.

**Source:** This is a proprietary index from BofA Merrill Lynch (now ICE BofA). Historical data is available via Bloomberg (`SMOVE Index`) or Refinitiv. FRED also carries the ICE BofA MOVE Index, which is the successor/equivalent:
- **FRED Series:** `MOVE` — https://fred.stlouisfed.org/series/MOVE

### 10. BCFF Survey — Forecaster Disagreement (DISAG)

**Paper usage:** Cross-sectional standard deviation of individual inflation forecasts 4 quarters ahead from the Blue Chip Financial Forecasts survey.

**Source:** Wolters Kluwer (publisher of Blue Chip Financial Forecasts). This is a proprietary subscription dataset. Individual forecasts are required to compute the cross-sectional dispersion. The Philadelphia Fed's Survey of Professional Forecasters (SPF) provides a publicly available alternative for disagreement measures:
- **SPF:** https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/survey-of-professional-forecasters

### 11. Unemployment Rate (UNEMP)

**Source (FRED):**
- **Series ID:** `UNRATE`
- **URL:** https://fred.stlouisfed.org/series/UNRATE

### 12. Consumer Confidence (CONF)

**Paper usage:** Conference Board Consumer Confidence Index.

**Source:** The Conference Board (proprietary). Available via Bloomberg, Refinitiv, or Haver Analytics. FRED carries the University of Michigan Consumer Sentiment Index as a public alternative:
- **FRED Series:** `UMCSENT` — https://fred.stlouisfed.org/series/UMCSENT

### 13. Core CPI Inflation (CPI)

**Paper usage:** Year-over-year core CPI inflation.

**Source (FRED):**
- **Series ID (SA):** `CPILFESL` — https://fred.stlouisfed.org/series/CPILFESL
- **Series ID (NSA):** `CPILFENS` — https://fred.stlouisfed.org/series/CPILFENS

### 14. Nominal Trade-Weighted Dollar (DOLLAR)

**Paper usage:** Nominal trade-weighted exchange value of the U.S. Dollar.

**Source (FRED):**
- **Series ID (Broad):** `DTWEXBGS` — https://fred.stlouisfed.org/series/DTWEXBGS
- **Series ID (Major currencies):** `DTWEXM` (discontinued; replaced by `DTWEXBGS`)

### 15. Blue Chip 5–10 Year Forward Inflation Forecast

**Paper usage:** Used as a survey benchmark for long-run inflation expectations (Figure 7). Observed semi-annually.

**Source:** Blue Chip Financial Forecasts (Wolters Kluwer). Proprietary. The Philadelphia Fed's SPF 10-year CPI inflation forecast is a close public alternative:
- **SPF Long-Range Forecasts:** https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/survey-of-professional-forecasters

### 16. Federal Funds Rate Futures Surprises

**Paper usage:** Section 5.3, measuring the surprise component of monetary policy on FOMC days.

**Source:** CME federal funds futures contracts. Proprietary tick data from Bloomberg or Refinitiv. Academic datasets of fed funds surprises are available from:
- **Ken Kuttner's website** or various replication packages
- **Refet Gürkaynak, Brian Sack, and Eric Swanson (2005)** provide an extended dataset of monetary policy surprises

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
| 7 | U.K. nominal & real gilt yields | Daily | Bank of England | Public | Excel |
| 8 | U.K. RPI | Monthly | ONS / DMO | Public | CSV |
| 9 | SMOVE / MOVE index | Daily | ICE BofA / FRED | Public (FRED) | CSV |
| 10 | BCFF disagreement | Monthly | Wolters Kluwer | Proprietary | — |
| 11 | Unemployment rate | Monthly | BLS / FRED | Public | CSV/API |
| 12 | Consumer confidence | Monthly | Conference Board | Proprietary | — |
| 13 | Core CPI (YoY) | Monthly | BLS / FRED | Public | CSV/API |
| 14 | Trade-weighted USD | Daily | Federal Reserve / FRED | Public | CSV/API |
| 15 | BCFF 5–10y inflation forecast | Semi-annual | Wolters Kluwer | Proprietary | — |
| 16 | Fed funds futures surprises | Event | CME / academic datasets | Mixed | — |

---

## Notes on Cross-Section and Time-Series Expansion

**Time series:** The paper sample runs 1999:01–2014:11. All public series (1–5, 7–8, 11, 13–14) continue to be updated and can be extended to the present. The binding constraint on the start date is the TIPS curve (available from 1999:01).

**Cross-section (nominal):** The paper uses n = 3, 6, 12, 24, ..., 120 months for PCA and n = 6, 12, 24, ..., 120 months for excess returns. Since the GSW nominal curve is well-identified out to 30 years, you can add maturities at 132, 144, ..., 360 months.

**Cross-section (TIPS):** The paper uses n = 24, ..., 120 months. With 20-year and 30-year TIPS now regularly issued, you can extend to 132, 144, ..., 240 or 360 months, though care is needed at the very long end where the Svensson extrapolation may be less reliable.

**Cross-section (U.K.):** The paper uses nominal n = 6, 12, ..., 120 months and real n = 60, ..., 120 months. The Bank of England publishes nominal yields up to 40 years and real yields where available. Consider extending both.
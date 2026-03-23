"""
Downloads and assembles the dataset required for the RealACM model from
Abrahams, Adrian, Crump, and Moench (2015) — "Decomposing Real and Nominal
Yield Curves" (NY Fed Staff Report No. 570).

Data sources:
    1. Nominal zero-coupon yields — GSW (2007), Federal Reserve
    2. TIPS zero-coupon yields   — GSW (2010), Federal Reserve
    3. CPI-U (NSA)               — FRED (series CPIAUCNS)
    4. Primary dealer volumes    — NY Fed FR2004 API (2013-04 onward)
    5. Composite liquidity indicator — derived from #2 fitting errors and #4

Output: sample_data/real_acm_data.xlsx
"""
import io
import numpy as np
import pandas as pd
import requests

# =========================================================================
# Nelson-Siegel-Svensson formula
# =========================================================================

def nss_yield(tau, beta0, beta1, beta2, beta3, tau1, tau2):
    """
    Compute the continuously compounded zero-coupon yield at maturity
    *tau* (in years) given Svensson parameters.  Returns percent.

    When tau2 is missing / invalid (e.g. -999.99) the fourth (beta3)
    term is dropped and the model reduces to Nelson-Siegel.
    """
    eps = 1e-12
    x1 = tau / (tau1 + eps)
    term1 = (1 - np.exp(-x1)) / x1
    term2 = term1 - np.exp(-x1)

    y = beta0 + beta1 * term1 + beta2 * term2

    if not (np.isnan(tau2) or tau2 <= 0):
        x2 = tau / (tau2 + eps)
        term3 = (1 - np.exp(-x2)) / x2 - np.exp(-x2)
        y += beta3 * term3

    return y


def nss_yield_vec(tau_years, params_row):
    """
    Evaluate the NSS curve at a vector of maturities for a single day.
    *params_row* must contain BETA0..BETA3, TAU1, TAU2.
    Returns a numpy array of yields (percent).
    """
    b0 = params_row["BETA0"]
    b1 = params_row["BETA1"]
    b2 = params_row["BETA2"]
    b3 = params_row["BETA3"]
    t1 = params_row["TAU1"]
    t2 = params_row["TAU2"]

    # Vectorised computation
    eps = 1e-12
    x1 = tau_years / (t1 + eps)
    term1 = (1 - np.exp(-x1)) / x1
    term2 = term1 - np.exp(-x1)

    y = b0 + b1 * term1 + b2 * term2

    if not (np.isnan(t2) or t2 <= 0):
        x2 = tau_years / (t2 + eps)
        term3 = (1 - np.exp(-x2)) / x2 - np.exp(-x2)
        y += b3 * term3

    return y


# =========================================================================
# 1.  Nominal zero-coupon yields (GSW 2007)
# =========================================================================

def download_nominal_yields(maturities_months=None):
    """
    Download the Gürkaynak-Sack-Wright (2007) nominal yield curve data,
    evaluate the Svensson curve at monthly maturities, and return a
    DataFrame of annualized continuously-compounded yields (in decimal).

    Parameters
    ----------
    maturities_months : list[int] or None
        Monthly maturities to evaluate.  Defaults to 1..120.
    """
    if maturities_months is None:
        maturities_months = list(range(1, 121))

    url = (
        "https://www.federalreserve.gov/data/yield-curve-tables/"
        "feds200628.csv"
    )
    print(f"Downloading nominal yields from {url} ...")
    r = requests.get(url, timeout=120)
    r.raise_for_status()

    # The CSV has ~9 metadata lines; the header row starts with "Date,BETA0,…"
    df_raw = pd.read_csv(
        io.StringIO(r.text),
        skiprows=9,
        index_col="Date",
        na_values="NA",
    )
    df_raw.index = pd.to_datetime(df_raw.index)
    df_raw.index.name = None

    # Replace the sentinel -999.99 in TAU2 with NaN
    df_raw["TAU2"] = df_raw["TAU2"].replace(-999.99, np.nan)

    # Keep only the Svensson parameters
    param_cols = ["BETA0", "BETA1", "BETA2", "BETA3", "TAU1", "TAU2"]
    params = df_raw[param_cols].dropna(subset=["BETA0", "TAU1"])

    tau_years = np.array(maturities_months) / 12.0

    # Evaluate NSS at each date
    yields_list = []
    for date, row in params.iterrows():
        try:
            y = nss_yield_vec(tau_years, row) / 100.0   # percent → decimal
        except Exception:
            y = np.full_like(tau_years, np.nan)
        yields_list.append(y)

    df_yields = pd.DataFrame(
        data=yields_list,
        index=params.index,
        columns=maturities_months,
    )

    # Filter from 1999 onward (TIPS data starts here)
    df_yields = df_yields.loc["1999-01-01":]

    print(f"  Nominal yields: {df_yields.shape[0]} days × "
          f"{df_yields.shape[1]} maturities")
    return df_yields


# =========================================================================
# 2.  TIPS (real) zero-coupon yields (GSW 2010)
# =========================================================================

def download_tips_yields(maturities_months=None):
    """
    Download the Gürkaynak-Sack-Wright (2010) TIPS yield curve data,
    evaluate the Svensson curve at monthly maturities, and return:
      - DataFrame of real zero-coupon yields (decimal)
      - Series of daily fitting-error proxy (absolute difference between
        NSS-evaluated and published TIPS yields at annual maturities)
    """
    if maturities_months is None:
        maturities_months = list(range(24, 121))

    url = (
        "https://www.federalreserve.gov/data/yield-curve-tables/"
        "feds200805.csv"
    )
    print(f"Downloading TIPS yields from {url} ...")
    r = requests.get(url, timeout=120)
    r.raise_for_status()

    # 18 metadata/header lines before the actual header row
    df_raw = pd.read_csv(
        io.StringIO(r.text),
        skiprows=18,
        index_col="Date",
        na_values="NA",
    )
    df_raw.index = pd.to_datetime(df_raw.index)
    df_raw.index.name = None

    # Svensson parameters
    param_cols = ["BETA0", "BETA1", "BETA2", "BETA3", "TAU1", "TAU2"]
    # TAU2 can be NA for Nelson-Siegel days
    params = df_raw[param_cols].copy()
    params["BETA3"] = params["BETA3"].fillna(0.0)
    params["TAU2"] = params["TAU2"].fillna(np.nan)
    params = params.dropna(subset=["BETA0", "TAU1"])

    tau_years = np.array(maturities_months) / 12.0

    # Evaluate NSS at monthly maturities
    yields_list = []
    for date, row in params.iterrows():
        try:
            y = nss_yield_vec(tau_years, row) / 100.0
        except Exception:
            y = np.full_like(tau_years, np.nan)
        yields_list.append(y)

    df_yields = pd.DataFrame(
        data=yields_list,
        index=params.index,
        columns=maturities_months,
    )

    # ---- Fitting-error proxy ----
    # The published yields (TIPSY02..TIPSY20) are the NSS-fitted values.
    # As a proxy for curve fitting quality we compute the daily RMSE between
    # the NSS-evaluated yields at published annual maturities and the
    # pre-computed published yields.  Non-trivial differences arise when
    # parameters are rounded or when the evaluation grid differs.
    published_cols = [c for c in df_raw.columns if c.startswith("TIPSY")]
    if published_cols:
        pub_mats_years = np.array(
            [int(c.replace("TIPSY", "")) for c in published_cols]
        )
        pub_mats_months = pub_mats_years * 12

        published_yields = df_raw.loc[params.index, published_cols].copy()
        published_yields.columns = pub_mats_months

        # Evaluate NSS at those same annual maturities
        nss_at_annual = []
        for date, row in params.iterrows():
            try:
                y = nss_yield_vec(pub_mats_years.astype(float), row)
            except Exception:
                y = np.full_like(pub_mats_years, np.nan, dtype=float)
            nss_at_annual.append(y)

        nss_df = pd.DataFrame(
            data=nss_at_annual,
            index=params.index,
            columns=pub_mats_months,
        )

        diff = (published_yields.values - nss_df.values)
        fitting_error = pd.Series(
            np.nanmean(np.abs(diff), axis=1),
            index=params.index,
            name="tips_fitting_error",
        )
    else:
        fitting_error = pd.Series(
            dtype=float, name="tips_fitting_error"
        )

    df_yields = df_yields.loc["1999-01-01":]
    fitting_error = fitting_error.loc["1999-01-01":]

    print(f"  TIPS yields: {df_yields.shape[0]} days × "
          f"{df_yields.shape[1]} maturities")
    return df_yields, fitting_error


# =========================================================================
# 3.  CPI-U, Not Seasonally Adjusted
# =========================================================================

def download_cpi():
    """
    Download CPI-U (NSA) from FRED.  Returns a monthly Series with
    DatetimeIndex.
    """
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCNS"
    print(f"Downloading CPI-U from {url} ...")
    r = requests.get(url, timeout=60)
    r.raise_for_status()

    df = pd.read_csv(
        io.StringIO(r.text),
        index_col="observation_date",
        parse_dates=True,
    )
    df.index.name = None
    cpi = df["CPIAUCNS"].rename("CPI")
    cpi = cpi.loc["1998-01-01":]  # keep a buffer before 1999

    print(f"  CPI-U: {len(cpi)} monthly observations, "
          f"{cpi.index[0].date()} to {cpi.index[-1].date()}")
    return cpi


# =========================================================================
# 4.  Primary dealer volumes — FR2004 (NY Fed API)
# =========================================================================

def download_fr2004_volumes():
    """
    Download weekly primary-dealer transaction volumes for nominal
    Treasuries (excl. TIPS) and TIPS from the NY Fed Markets API.

    The API only provides data from approximately 2013-04 onward.

    Returns a DataFrame with columns ['treasury_volume', 'tips_volume']
    and a weekly DatetimeIndex.
    """
    base = "https://markets.newyorkfed.org/api/pd/get"

    dfs = {}
    for keyid, col in [
        ("PDGSWOEXTTOT", "treasury_volume"),
        ("PDTIPSTOT", "tips_volume"),
    ]:
        url = f"{base}/{keyid}.json"
        print(f"Downloading {keyid} from NY Fed API ...")
        r = requests.get(url, timeout=60)
        r.raise_for_status()

        records = r.json()["pd"]["timeseries"]
        if not records:
            print(f"  WARNING: No data returned for {keyid}")
            continue

        s = pd.DataFrame(records)
        s["asofdate"] = pd.to_datetime(s["asofdate"])
        s = s.set_index("asofdate").sort_index()
        s["value"] = pd.to_numeric(s["value"], errors="coerce")
        dfs[col] = s["value"].rename(col)

    if not dfs:
        print("  WARNING: No FR2004 data available")
        return pd.DataFrame()

    df = pd.concat(dfs.values(), axis=1)
    print(f"  FR2004 volumes: {len(df)} weeks, "
          f"{df.index[0].date()} to {df.index[-1].date()}")
    return df


# =========================================================================
# 5.  Composite liquidity indicator
# =========================================================================

def build_liquidity_indicator(
    tips_fitting_error,
    fr2004_volumes,
):
    """
    Construct the composite TIPS liquidity factor as described in
    Section 4.1 of the paper:

    1. Standardise TIPS fitting error and the Treasury/TIPS volume
       ratio (13-week MA).
    2. Equal-weighted average of the two standardised series.
    3. Shift so the minimum is zero (illiquidity can only raise yields).

    Where FR2004 volume data is not available (pre-2013), only the
    fitting-error component is used (single-indicator proxy).

    Returns a daily Series.
    """
    # --- Fitting error component (daily → end-of-week) ---
    fe = tips_fitting_error.copy()
    fe_std = (fe - fe.mean()) / fe.std()

    if fr2004_volumes.empty:
        print("  Liquidity indicator: fitting-error proxy only (no FR2004)")
        liq = fe_std - fe_std.min()
        liq.name = "liquidity"
        return liq

    # --- Volume ratio component ---
    vol = fr2004_volumes.copy()
    vol = vol.dropna()
    ratio = vol["treasury_volume"] / vol["tips_volume"]
    ratio_ma = ratio.rolling(window=13, min_periods=1).mean()
    ratio_std = (ratio_ma - ratio_ma.mean()) / ratio_ma.std()

    # Align to common daily index via forward-fill
    all_dates = fe_std.index
    ratio_daily = ratio_std.reindex(all_dates, method="ffill")

    # Build composite where both series overlap
    has_vol = ratio_daily.notna()
    composite = pd.Series(np.nan, index=all_dates, name="liquidity")

    # Where both available: equal-weighted average
    both = has_vol & fe_std.notna()
    composite[both] = 0.5 * (fe_std[both] + ratio_daily[both])

    # Where only fitting error available: use it alone
    only_fe = ~has_vol & fe_std.notna()
    composite[only_fe] = fe_std[only_fe]

    # Shift so minimum is zero
    composite = composite - composite.min()
    print(f"  Liquidity indicator: {composite.notna().sum()} daily values")
    return composite


# =========================================================================
# Main
# =========================================================================

def main():
    print("=" * 60)
    print("Building RealACM dataset")
    print("=" * 60)
    print()

    # 1. Nominal yields (maturities 1–120 months)
    nominal = download_nominal_yields(list(range(1, 121)))
    print()

    # 2. TIPS yields (maturities 24–120 months) + fitting error
    tips, fitting_error = download_tips_yields(list(range(24, 121)))
    print()

    # 3. CPI-U
    cpi = download_cpi()
    print()

    # 4. FR2004 volumes
    fr2004 = download_fr2004_volumes()
    print()

    # 5. Composite liquidity indicator
    liquidity = build_liquidity_indicator(fitting_error, fr2004)
    print()

    # ---- Save to Excel ----
    out_path = "sample_data/real_acm_data.xlsx"
    print(f"Saving to {out_path} ...")
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        nominal.to_excel(writer, sheet_name="nominal_yields")
        tips.to_excel(writer, sheet_name="tips_yields")
        cpi.to_frame().to_excel(writer, sheet_name="cpi")
        liquidity.to_frame().to_excel(writer, sheet_name="liquidity")

    print("Done.")
    print()
    print("Summary:")
    print(f"  Nominal yields: {nominal.shape}")
    print(f"  TIPS yields:    {tips.shape}")
    print(f"  CPI-U:          {len(cpi)} months")
    print(f"  Liquidity:      {liquidity.notna().sum()} days")


if __name__ == "__main__":
    main()

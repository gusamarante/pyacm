"""
This file runs the RealACM model on sample US data (nominal Treasuries + TIPS).
It replicates the joint term structure model from:

    Abrahams, Adrian, Crump, and Moench. "Decomposing Real and Nominal Yield
    Curves." Journal of Monetary Economics 84 (2016): 182-200.

The model decomposes breakeven inflation into:
    - Expected inflation (risk-neutral)
    - Inflation risk premium (IRP = TP_N - TP_R)
    - Liquidity premium (captured by the liquidity factor in the state vector)

The results are very close to the authors' original results, but not match
exactly as the sample data for the liquidity factor does not have a long enough
history anymore
"""
import pandas as pd
import matplotlib.pyplot as plt
from pyacm import RealACM


# ====================
# ===== Load Data ====
# ====================
xl = pd.ExcelFile("sample_data/real_acm_data.xlsx")

nominal_curve = pd.read_excel(xl, sheet_name="nominal_yields", index_col=0, parse_dates=True)
nominal_curve.columns = nominal_curve.columns.astype(int)

tips_curve = pd.read_excel(xl, sheet_name="tips_yields", index_col=0, parse_dates=True)
tips_curve.columns = tips_curve.columns.astype(int)

liquidity = pd.read_excel(xl, sheet_name="liquidity", index_col=0, parse_dates=True).iloc[:, 0]

cpi = pd.read_excel(xl, sheet_name="cpi", index_col=0, parse_dates=True).iloc[:, 0]

# Restrict to the paper's sample period: January 1999 – November 2014 (T=191 months)
START = "1999-01-01"
END = "2014-11-30"
nominal_curve = nominal_curve.loc[START:END]
tips_curve = tips_curve.loc[START:END]
liquidity = liquidity.loc[START:END]
cpi = cpi.loc[START:END]


# =========================
# ===== Fit the Model =====
# =========================
# Maturities used in the SUR return regression (paper uses N_N=11, N_R=9)
selected_maturities_n = [6, 12, 24, 36, 48, 60, 72, 84, 96, 108, 120]
selected_maturities_r = [24, 36, 48, 60, 72, 84, 96, 108, 120]

acm = RealACM(
    nominal_curve=nominal_curve,
    real_curve=tips_curve,
    liquidity=liquidity,
    cpi=cpi,
    n_factors_n=3,
    n_factors_r=2,
    selected_maturities_n=selected_maturities_n,
    selected_maturities_r=selected_maturities_r,
)


# ==================
# ===== Charts =====
# ==================
mat = 120  # 10-year maturity

size = 5
fig = plt.figure(figsize=(size * (16 / 7), size * 2))
fig.suptitle(f"RealACM — US Treasury & TIPS Decomposition ({mat/12}-Year), 1999:01–2014:11", fontsize=13)

grid_kw = dict(color="grey", linestyle="-", linewidth=0.5, alpha=0.5)
tick_kw = dict(rotation=90, axis="x")


# --- Panel 1: Nominal yield fit ---
ax1 = plt.subplot2grid((2, 2), (0, 0))
ax1.plot(nominal_curve[mat], label="Observed Nominal", lw=1)
ax1.plot(acm.miy_n[mat], label="Fitted Nominal", lw=1, ls="--")
ax1.set_title(f"{mat/12}Y Nominal Yield: Observed vs Fitted")
ax1.xaxis.grid(**grid_kw)
ax1.yaxis.grid(**grid_kw)
ax1.tick_params(**tick_kw)
ax1.legend()

# --- Panel 2: TIPS yield fit ---
ax2 = plt.subplot2grid((2, 2), (0, 1))
ax2.plot(tips_curve[mat], label="Observed TIPS", lw=1)
ax2.plot(acm.miy_r[mat], label="Fitted Real", lw=1, ls="--")
ax2.set_title(f"{mat/12}Y Real Yield: Observed vs Fitted")
ax2.xaxis.grid(**grid_kw)
ax2.yaxis.grid(**grid_kw)
ax2.tick_params(**tick_kw)
ax2.legend()

# --- Panel 3: Nominal yield decomposition ---
ax3 = plt.subplot2grid((2, 2), (1, 0))
ax3.plot(nominal_curve[mat], label="Nominal Yield", lw=1)
ax3.plot(acm.rny_n[mat], label="Risk-Neutral Nominal", lw=1)
ax3.plot(acm.tp_n[mat], label="Nominal TP", lw=1)
ax3.set_title(f"{mat/12}Y Nominal Decomposition")
ax3.xaxis.grid(**grid_kw)
ax3.yaxis.grid(**grid_kw)
ax3.tick_params(**tick_kw)
ax3.legend()

# --- Panel 4: Breakeven decomposition ---
ax4 = plt.subplot2grid((2, 2), (1, 1))
ax4.plot(acm.breakeven[mat], label="Breakeven", lw=1)
ax4.plot(acm.irp[mat], label="Inflation Risk Premium", lw=1)
ax4.plot(acm.breakeven[mat] - acm.irp[mat], label="Expected Inflation (RN)", lw=1, ls="--")
ax4.set_title(f"{mat/12}Y Breakeven Decomposition")
ax4.xaxis.grid(**grid_kw)
ax4.yaxis.grid(**grid_kw)
ax4.tick_params(**tick_kw)
ax4.legend()

plt.tight_layout()
plt.show()


# ===================================
# ===== Replication of Figure 7 =====
# ====================================
fwd = acm.forward_rates_ts(t1=5, t2=10)

# --- Plot ---
size = 5
fig7 = plt.figure(figsize=(size * (16 / 7), size * 2))
fig7.suptitle(
    "Figure 7: Treasury and TIPS Term Premia — 5–10Y Forward Decomposition, 1999:01–2014:11",
    fontsize=12,
)

# Panel 1: Treasury Term Premium
ax1 = plt.subplot2grid((2, 2), (0, 0))
ax1.plot(fwd["miy_n"], label="Fitted Nominal Yield",       lw=1, color="blue")
ax1.plot(fwd["rny_n"], label="Risk-Neutral Nominal Yield", lw=1, ls="--", color="green")
ax1.plot(fwd["tp_n"],  label="Nominal Term Premium",       lw=1, color="red")
ax1.plot(fwd["liq_n"], label="Liquidity Component",        lw=1, ls="-.", color="black")
ax1.set_title("Treasury Term Premium")
ax1.xaxis.grid(**grid_kw)
ax1.yaxis.grid(**grid_kw)
ax1.tick_params(**tick_kw)
ax1.legend(fontsize=7)

# Panel 2: TIPS Term Premium
ax2 = plt.subplot2grid((2, 2), (0, 1))
ax2.plot(fwd["miy_r"], label="Fitted Real Yield",          lw=1, color="blue")
ax2.plot(fwd["rny_r"], label="Risk-Neutral Real Yield",    lw=1, ls="--", color="green")
ax2.plot(fwd["tp_r"],  label="Real Term Premium",          lw=1, color="red")
ax2.plot(fwd["liq_r"], label="Liquidity Component",        lw=1, ls="-.", color="black")
ax2.set_title("TIPS Term Premium")
ax2.xaxis.grid(**grid_kw)
ax2.yaxis.grid(**grid_kw)
ax2.tick_params(**tick_kw)
ax2.legend(fontsize=7)

# Panel 3: Term Premium Comparison
ax3 = plt.subplot2grid((2, 2), (1, 0))
ax3.plot(fwd["tp_n"], label="Nominal Term Premium", lw=1, color="red")
ax3.plot(fwd["tp_r"], label="Real Term Premium",    lw=1, color="green")
ax3.plot(fwd["irp"],  label="IRP",                  lw=1, color="black")
ax3.set_title("Term Premium Comparison")
ax3.xaxis.grid(**grid_kw)
ax3.yaxis.grid(**grid_kw)
ax3.tick_params(**tick_kw)
ax3.legend()

# Panel 4: Liquidity-adjusted Breakeven Decomposition
ax4 = plt.subplot2grid((2, 2), (1, 1))
ax4.plot(fwd["liq_adj_be"],    label="Liq-Adj Breakeven",       lw=1, color="olive")
ax4.plot(fwd["irp"],           label="IRP",                     lw=1, color="black")
ax4.plot(fwd["exp_inflation"], label="Expected Inflation (RN)", lw=1, ls="--", color="red")
ax4.set_title("Liq-Adj Breakeven Decomposition")
ax4.xaxis.grid(**grid_kw)
ax4.yaxis.grid(**grid_kw)
ax4.tick_params(**tick_kw)
ax4.legend()

plt.tight_layout()
plt.show()

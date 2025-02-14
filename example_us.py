from pyacm import NominalACM
import pandas as pd
import matplotlib.pyplot as plt


ylds_d = pd.read_excel("sample_data/us_data.xlsx", index_col=0, sheet_name="daily")
ylds_d.index = pd.to_datetime(ylds_d.index)
ylds_d = ylds_d / 100

ylds_m = pd.read_excel("sample_data/us_data.xlsx", index_col=0, sheet_name="monthly")
ylds_m.index = pd.to_datetime(ylds_m.index)
ylds_m = ylds_m.resample("M").last()
ylds_m = ylds_m / 100

acm = NominalACM(
    curve=ylds_d,
    curve_m=ylds_m,
    n_factors=5,
    selected_maturities=[6, 12, 24, 36, 48, 60, 72, 84, 96, 108, 120],
)

# CHART
size = 7
fig = plt.figure(figsize=(size * (16 / 7.3), size))

ax = plt.subplot2grid((1, 2), (0, 0))
ax.plot(ylds_d[120], label="Actual Yield", lw=1)
ax.plot(acm.miy[120], label="Fitted Yield", lw=1, ls='--')
ax.set_title("10-Year Model Fit")
ax.xaxis.grid(color="grey", linestyle="-", linewidth=0.5, alpha=0.5)
ax.yaxis.grid(color="grey", linestyle="-", linewidth=0.5, alpha=0.5)
ax.tick_params(rotation=90, axis="x")
ax.legend(loc="upper right")

ax = plt.subplot2grid((1, 2), (0, 1))
ax.plot(ylds_d[120], label="Yield", lw=1)
ax.plot(acm.rny[120], label="Risk Neutral Yield", lw=1)
ax.plot(acm.tp[120], label="Term Premium", lw=1)
ax.set_title("10-Year Yield Decomposition")
ax.xaxis.grid(color="grey", linestyle="-", linewidth=0.5, alpha=0.5)
ax.yaxis.grid(color="grey", linestyle="-", linewidth=0.5, alpha=0.5)
ax.tick_params(rotation=90, axis="x")
ax.legend(loc="upper right")

plt.tight_layout()
plt.show()

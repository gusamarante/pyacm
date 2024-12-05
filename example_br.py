from pyacm import NominalACM
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd


# Read and plot data
yield_curve = pd.read_csv(
    "https://raw.githubusercontent.com/gusamarante/pyacm/refs/heads/main/sample_data/di%20monthly%20maturities.csv",
    index_col=0,
)
yield_curve = yield_curve.iloc[:, :121]  # maturities up to 10y
yield_curve = yield_curve.dropna()
yield_curve.index = pd.to_datetime(yield_curve.index)
yield_curve = yield_curve[yield_curve.index >= "2007-03-01"]


# Plot the Series of selcted maturities
yield_curve[["12m", "24m", "60m", "120m"]].plot(legend=True, title="Yields for Selected Maturities", grid=True)
plt.tight_layout()
plt.show()

# Run the model
acm = NominalACM(
    curve=yield_curve,
    n_factors=5,
)

# Excess returns of synthetic bonds
acm.rx_m[["12m", "24m", "60m"]].plot(legend=True, title="Monthly excess returns of synthetic bonds", grid=True)
plt.tight_layout()
plt.show()


# Principal components
acm.pc_factors_d.plot(legend=True, title="Principal Components of the Curve", grid=True)
plt.tight_layout()
plt.show()


# Fitted VS Observed
fig = plt.figure(figsize=(5 * (16 / 9), 5))
ax = plt.subplot2grid((1, 2), (0, 0))
mat = "24m"
ax.plot(acm.curve[mat], label='Observed')
ax.plot(acm.miy[mat], label='Fitted')
ax.set_title(f"{mat} DI Futures")
ax.xaxis.grid(color="grey", linestyle="-", linewidth=0.5, alpha=0.5)
ax.yaxis.grid(color="grey", linestyle="-", linewidth=0.5, alpha=0.5)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax.tick_params(rotation=90, axis="x")
ax.legend(frameon=True, loc="best")

ax = plt.subplot2grid((1, 2), (0, 1))
mat = "60m"
ax.plot(acm.curve[mat], label='Observed')
ax.plot(acm.miy[mat], label='Fitted')
ax.set_title(f"{mat} DI Futures")
ax.xaxis.grid(color="grey", linestyle="-", linewidth=0.5, alpha=0.5)
ax.yaxis.grid(color="grey", linestyle="-", linewidth=0.5, alpha=0.5)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax.tick_params(rotation=90, axis="x")
ax.legend(frameon=True, loc="best")

plt.tight_layout()
plt.show()


# Risk Neutral vs market
fig = plt.figure(figsize=(5 * (16 / 9), 5))
ax = plt.subplot2grid((1, 2), (0, 0))
mat = "24m"
ax.plot(acm.curve[mat], label='Observed')
ax.plot(acm.rny[mat], label='Risk-Neutral')
ax.set_title(f"{mat} DI Futures VS Risk-Neutral")
ax.xaxis.grid(color="grey", linestyle="-", linewidth=0.5, alpha=0.5)
ax.yaxis.grid(color="grey", linestyle="-", linewidth=0.5, alpha=0.5)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax.tick_params(rotation=90, axis="x")
ax.legend(frameon=True, loc="best")

ax = plt.subplot2grid((1, 2), (0, 1))
mat = "60m"
ax.plot(acm.curve[mat], label='Observed')
ax.plot(acm.rny[mat], label='Risk-Neutral')
ax.set_title(f"{mat} DI Futures VS Risk-Neutral")
ax.xaxis.grid(color="grey", linestyle="-", linewidth=0.5, alpha=0.5)
ax.yaxis.grid(color="grey", linestyle="-", linewidth=0.5, alpha=0.5)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax.tick_params(rotation=90, axis="x")
ax.legend(frameon=True, loc="best")

plt.tight_layout()
plt.show()

# Term premium
fig = plt.figure(figsize=(5 * (16 / 9), 5))
ax = plt.subplot2grid((1, 1), (0, 0))
ax.plot(acm.tp["24m"], label='24m')
ax.plot(acm.tp["60m"], label='60m')
ax.set_title(f"Term Premium for DI Futures")
ax.xaxis.grid(color="grey", linestyle="-", linewidth=0.5, alpha=0.5)
ax.yaxis.grid(color="grey", linestyle="-", linewidth=0.5, alpha=0.5)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax.tick_params(rotation=90, axis="x")
ax.legend(frameon=True, loc="best")

plt.tight_layout()
plt.show()

# Term Premium VS Expected Returns
fig = plt.figure(figsize=(5 * (16 / 9), 5))
ax = plt.subplot2grid((1, 1), (0, 0))
ax.plot(acm.tp["60m"], label='Term Premium')
ax.plot(acm.er_hist_d["60m"], label='Expected Return')
ax.set_title(f"Term Premium VS Expected Return")
ax.xaxis.grid(color="grey", linestyle="-", linewidth=0.5, alpha=0.5)
ax.yaxis.grid(color="grey", linestyle="-", linewidth=0.5, alpha=0.5)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax.tick_params(rotation=90, axis="x")
ax.legend(frameon=True, loc="best")

plt.tight_layout()
plt.show()


# Term Premium VS Expected Returns
fig = plt.figure(figsize=(5 * (16 / 9), 5))

fwd_curves = acm.fwd_curve("2024-07-05")
fwd_curves = fwd_curves.reset_index(drop=True)
fwd_curves.index = fwd_curves.index + 1

ax = plt.subplot2grid((1, 1), (0, 0))
ax.plot(fwd_curves, label=fwd_curves.columns)
ax.set_title(f"Forward Curves")
ax.set_xlabel("Maturity in Months")
ax.xaxis.grid(color="grey", linestyle="-", linewidth=0.5, alpha=0.5)
ax.yaxis.grid(color="grey", linestyle="-", linewidth=0.5, alpha=0.5)
ax.tick_params(rotation=90, axis="x")
ax.legend(frameon=True, loc="best")

plt.tight_layout()
plt.show()

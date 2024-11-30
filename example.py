from pyacm import NominalACM

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# Read and plot data
yield_curve = pd.read_csv(
    "sample_data/di monthly maturities.csv",
    index_col=0,
)
yield_curve = yield_curve.iloc[:, :120]  # maturities up to 10y
yield_curve = yield_curve.dropna()
yield_curve.index = pd.to_datetime(yield_curve.index)

yield_curve[["12m", "24m", "60m", "120m"]].plot(legend=True, title="Yields for Selected Maturities", grid=True)
plt.tight_layout()
plt.show()
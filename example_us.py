from pyacm import NominalACM
import pandas as pd
import matplotlib.pyplot as plt

# TODO this input is not matching the matlab version
ylds_d = pd.read_excel("sample_data/us_data.xlsx", index_col=0, sheet_name="daily")
ylds_d.index = pd.to_datetime(ylds_d.index)
ylds_d = ylds_d.iloc[:-10]
acm = NominalACM(
    curve=ylds_d,
    n_factors=5,
    selected_maturities=[6, 12, 24, 36, 48, 60, 72, 84, 96, 108, 120]
)

acm.tp[119].plot()
plt.show()

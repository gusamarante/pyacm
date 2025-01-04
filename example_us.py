from pyacm import NominalACM
import pandas as pd
import matplotlib.pyplot as plt


ylds_d = pd.read_excel("sample_data/us_data.xlsx", index_col=0, sheet_name="daily")
ylds_d.index = pd.to_datetime(ylds_d.index)

ylds_m = pd.read_excel("sample_data/us_data.xlsx", index_col=0, sheet_name="monthly")
ylds_m.index = pd.to_datetime(ylds_m.index)

acm = NominalACM(
    curve=ylds_d,
    curve_m=ylds_m,
    n_factors=5,
    selected_maturities=[6, 12, 24, 36, 48, 60, 72, 84, 96, 108, 120]
)

acm.tp[119].plot()
plt.show()

from pyacm import NominalACM
import pandas as pd
import matplotlib.pyplot as plt

ylds_d = pd.read_excel("sample_data/us_data.xlsx", index_col=0, sheet_name="daily")
ylds_d.index = pd.to_datetime(ylds_d.index)

acm = NominalACM(
    curve=ylds_d,
    n_factors=5,
)

acm.tp[119].plot()
plt.show()

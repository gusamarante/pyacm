"""
Generate point-in-time estimates.

For each date, rerun the model and save the latest estimate of expected return
and term premium
"""
from tqdm import tqdm
import pandas as pd
from pyacm import NominalACM


min_obs = 252

# Read the data
yield_curve = pd.read_csv(
    "sample_data/di monthly maturities.csv",
    index_col=0,
)
yield_curve = yield_curve.iloc[:, :121]  # maturities up to 10y
yield_curve = yield_curve.dropna()
yield_curve.index = pd.to_datetime(yield_curve.index)
yield_curve = yield_curve[yield_curve.index >= "2007-03-01"]

tp = pd.DataFrame(columns=yield_curve.columns)
er = pd.DataFrame(columns=yield_curve.columns)

for d in tqdm(yield_curve.index):

    aux_curve = yield_curve.loc[:d]
    if aux_curve.shape[0] < min_obs:
        continue

    acm = NominalACM(
        curve=aux_curve,
        n_factors=5,
    )

    tp.loc[d] = acm.tp.loc[d]
    er.loc[d] = acm.er_hist_d.loc[d]

tp.to_csv("sample_data/pit_tp.csv")
er.to_csv("sample_data/pit_er.csv")

# TODO currently working on this

import pandas as pd
import matplotlib.pyplot as plt
from pyacm import RealACM






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
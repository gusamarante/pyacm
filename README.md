[paper_website_nominal]: https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr340.pdf
[paper_website_real]: https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr570.pdf

# pyacm
Python implementation of the ACM Term Premium models
- **Nominal** version from ["Pricing the Term Structure with Linear Regressions" from Adrian, Crump and Moench (2013)][paper_website_nominal].
- **Real** version from ["Decomposing Real and Nominal Yield Curves" from Abrahams, Adrian, Crump and Moench (2015)][paper_website_real].

The `NominalACM` class prices the time series and cross-section of the term 
structure of interest rates using a three-step linear regression approach.
Computations are fast, even with a large number of pricing factors. The object 
carries all the relevant variables as atributes:
- The yield curve itself
- The excess returns from the synthetic zero coupon bonds
- The principal components of the curve used as princing factors
- Risk premium parameter estimates
- Yields fitted by the model
- Risk-neutral yields
- Term premium
- Historical in-sample expected returns 
- Expected return loadings

The `RealACM` class extends the nominal model to jointly price nominal and real 
(inflation-linked) yield curves. It decomposes nominal yields into expected real 
rates, expected inflation, real term premia, inflation risk premia, and a 
liquidity premium. The state vector combines nominal PCs, orthogonalized real 
PCs, and an observable liquidity factor. Key attributes include:
- Nominal and real model-implied yields (`miy_n`, `miy_r`)
- Nominal and real risk-neutral yields (`rny_n`, `rny_r`)
- Nominal and real term premia (`tp_n`, `tp_r`)
- Breakeven inflation and inflation risk premium (`breakeven`, `irp`)
- Forward rate decompositions via `forward_rates_ts` and `forward_rates_cs`


# Instalation
```bash
pip install pyacm
```


# Usage
## Nominal

```python
from pyacm import NominalACM

acm = NominalACM(
    curve=yield_curve,
    n_factors=5,
)
```
The tricky part of using this model is getting the correct data format. The 
`yield_curve` dataframe in the expression above requires:
- Annualized log-yields for zero-coupon bonds
- Observations (index) must be in either monthly or daily frequency
- Maturities (columns) must be equally spaced in **monthly** frequency and start 
at month 1. This means that you need to construct a bootstraped curve for every 
date and interpolate it at fixed monthly maturities

## Real / Inflation-Linked

```python
from pyacm import RealACM

acm = RealACM(
    nominal_curve=nominal_curve,
    real_curve=real_curve,
    liquidity=liquidity,
    cpi=cpi,
    n_factors_n=3,
    n_factors_r=2,
    selected_maturities_n=[6, 12, 24, 36, 48, 60, 72, 84, 96, 108, 120],
    selected_maturities_r=[24, 36, 48, 60, 72, 84, 96, 108, 120],
)
```
In addition to the nominal curve requirements above, the `RealACM` class needs:
- `real_curve`: annualized log-yields for real (inflation-linked) zero-coupon 
  bonds. Columns must be consecutive integers in monthly maturities (e.g. 24 to 120)
- `liquidity`: a positive `pd.Series` with an observable liquidity proxy 
  (e.g. fitting errors, relative trading volumes, or a composite index)
- `cpi`: a monthly `pd.Series` with the consumer price index level, used to 
  compute realized inflation
- `selected_maturities_n` and `selected_maturities_r` control which maturities 
  enter the return regressions for the nominal and real curves, respectively


# Examples
## Nominal
Updated estimates for the US are available on the [NY FED website](https://www.newyorkfed.org/research/data_indicators/term-premia-tabs#/overview). 
The file [`example_us`](https://github.com/gusamarante/pyacm/blob/main/example_us.py) reproduces the original outputs using the same 
dataset as the authors.

The jupyter notebook [`example_br`](https://github.com/gusamarante/pyacm/blob/main/example_br.ipynb) 
contains an example application to the Brazilian DI futures curve that 
showcases all the available methods and attributes.

<p align="center">
  <img src="https://raw.githubusercontent.com/gusamarante/pyacm/refs/heads/main/images/DI%20term%20premium.png" alt="DI Term Premium"/>
  <img src="https://raw.githubusercontent.com/gusamarante/pyacm/refs/heads/main/images/DI%20observed%20vs%20risk%20neutral.png" alt="Observed VS Risk Neutral"/>
</p>

## Real
The file [`example_real_us`](https://github.com/gusamarante/pyacm/blob/main/example_real_us.py) 
replicates the joint Treasury-TIPS decomposition from Abrahams, Adrian, Crump 
and Moench (2016) using US data.

The jupyter notebook [`example_real_br`](https://github.com/gusamarante/pyacm/blob/main/example_real_br.ipynb) 
applies the `RealACM` model to Brazilian nominal (LTN/NTN-F) and 
inflation-linked (NTN-B) yield curves, decomposing yields into expected real 
rates, expected inflation, real term premia, inflation risk premia, and a 
liquidity premium.


# Original Article
> Adrian, Tobias and Crump, Richard K. and Moench, Emanuel, 
> Pricing the Term Structure with Linear Regressions (April 11, 2013). 
> FRB of New York Staff Report No. 340

> Abrahams, Michael and Adrian, Tobias and Crump, Richard K. and Moench, Emanuel, 
> Decomposing Real and Nominal Yield Curves (February, 2015).
> FRB of New York Staff Report No. 570

I would like to thank Emanuel Moench for sharing his original MATLAB code in 
order to replicate these results.

# Citation
> Gustavo Amarante (2025). pyacm: Python Implementation of the ACM Term Premium 
> Model. Retrieved from https://github.com/gusamarante/pyacm

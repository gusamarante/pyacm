[paper_website]: https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr340.pdf


# pyacm
Implementation of ["Pricing the Term Structure with Linear Regressions" from 
Adrian, Crump and Moench (2013)][paper_website].

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


# Instalation
```bash
pip install pyacm
```


# Usage
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


# Examples
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

# Original Article
> Adrian, Tobias and Crump, Richard K. and Moench, Emanuel, 
> Pricing the Term Structure with Linear Regressions (April 11, 2013). 
> FRB of New York Staff Report No. 340, 
> Available at SSRN: https://ssrn.com/abstract=1362586 or http://dx.doi.org/10.2139/ssrn.1362586

I would like to thank Emanuel Moench for sharing his original MATLAB code in 
order to perfectly replicate these results.

# Citation
> Gustavo Amarante (2025). pyacm: Python Implementation of the ACM Term Premium 
> Model. Retrieved from https://github.com/gusamarante/pyacm
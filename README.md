[paper_website]: https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr340.pdf
[inference_atribute]: https://github.com/gusamarante/pyacm/blob/ba641c14e450fc83d22db4ef5e60eadbd489b351/pyacm/acm.py#L203

**<span style="color:red">STILL UNDER DEVELOPMENT</span>**

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
- Expected return loadings
- Hypothesis testing (Not sure if correct, more info observations below)


# Instalation
```bash
pip install pyacm
```

# Example
The tricky part is getting the correct data format. The model works with 
annualized log-yields for zero-coupon bonds, observed at daily or monthly 
frequency. Maturities must be equally spaced in monthly frequency and start 
at month 1. This means that you need to construct a bootstraped curve for every
date and interpolate it at fixed monthly maturities.

MORE SOON...


# Observations
I am not completely sure that computations in the [inferences attributes][inference_atribute] 
are correct. If you find any mistakes, please open a pull request following the contributing 
guidelines.

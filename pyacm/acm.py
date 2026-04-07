import numpy as np
import pandas as pd

from numpy.linalg import inv
from scipy.optimize import minimize
from sklearn.decomposition import PCA
from sklearn.linear_model import LinearRegression
from statsmodels.tools.tools import add_constant


class NominalACM:
    """
    This class implements the model from the article:

        Adrian, Tobias, Richard K. Crump, and Emanuel Moench. “Pricing the
        Term Structure with Linear Regressions.” SSRN Electronic Journal,
        2012. https://doi.org/10.2139/ssrn.1362586.

    It handles data transformation, estimates parameters and generates the
    relevant outputs. The version of the article that was published by the NY
    FED is not 100% explicit on how the data is being manipulated, but I found
    an earlier version of the paper on SSRN where the authors go deeper into
    the details on how everything is being estimated:
        - Data for zero yields uses monthly maturities starting from month 1
        - All principal components and model parameters are estiamted with data
          resampled to a monthly frequency, averaging observations in each
          month.
        - To get daily / real-time estimates, the factor loadings estimated
          from the monthly frquency are used to transform the daily data.

    Attributes
    ----------
    n_factors: int
        number of principal components used

    curve: pandas.DataFrame
        Raw data of the yield curve

    curve_monthly: pandas.DataFrame
        Yield curve data resampled to a monthly frequency by averageing
        the observations

    t_m: int
        Number of observations in the monthly timeseries dimension

    t_d: int
        Number of observations in the daily timeseries dimension

    n: int
        Number of observations in the cross-sectional dimension, the number of
        maturities available

    rx_m: pd.DataFrame
        Excess returns in monthly frquency

    pc_factors_m: pandas.DataFrame
        Principal components in monthly frequency

    pc_loadings_m: pandas.DataFrame
        Factor loadings of the monthly PCs

    pc_explained_m: pandas.Series
        Percent of total variance explained by each monthly principal component

    pc_factors_d: pandas.DataFrame
        Principal components in daily frequency

    mu, phi, Sigma, v: numpy.array
        Estimates of the VAR(1) parameters, the first stage of estimation.
        The names are the same as the original paper

    beta: numpy.array
        Estimates of the risk premium equation, the second stage of estimation.
        The name is the same as the original paper

    lambda0, lambda1: numpy.array
        Estimates of the price of risk parameters, the third stage of
        estimation.

    delta0, delta1: numpy.array
        Estimates of the short rate equation coefficients.

    A, B: numpy.array
        Affine coefficients for the fitted yields of different maturities

    Arn, Brn: numpy.array
        Affine coefficients for the risk neutral yields of different maturities

    miy: pandas.DataFrame
        Model implied / fitted yields

    rny: pandas.DataFrame
        Risk neutral yields

    tp: pandas.DataFrame
        Term premium estimates

    er_loadings: pandas.DataFrame
        Loadings of the expected reutrns on the principal components

    er_hist: pandas.DataFrame
        Historical estimates of expected returns, computed in-sample.
    """

    def __init__(
            self,
            curve,
            curve_m=None,
            n_factors=5,
            selected_maturities=None,
    ):
        """
        Runs the baseline varsion of the ACM term premium model. Works for data
        with monthly frequency or higher.

        Parameters
        ----------
        curve : pandas.DataFrame
            Annualized log-yields. Maturities (columns) must start at month 1
            and be equally spaced in monthly frequency. Column labels must be
            integers from 1 to n. Observations (index) must be a pandas
            DatetimeIndex with daily frequency.

        curve_m: pandas.DataFrame
            Annualized log-yields in monthly frequency to be used for the
            parameters estimates. This is here in case the user wants to use a
            different curve for the parameter estimation. If None is passed,
            the input `curve` is resampled to monthly frequency. If something
            is passed, maturities (columns) must start at month 1 and be
            equally spaced in monthly frequency. Column labels must be
            integers from 1 to n. Observations (index) must be a pandas
            DatetimeIndex with monthly frequency.

        n_factors : int
            number of principal components to used as state variables.

        selected_maturities: list of int
            the maturities to be considered in the parameter estimation steps.
            If None is passed, all the maturities are considered. The user may
            choose smaller set of yields to consider due to, for example,
            liquidity and representativeness of certain maturities.
        """

        self._assertions(curve, curve_m, selected_maturities)



        self.n_factors = n_factors
        self.curve = curve

        if selected_maturities is None:
            self.selected_maturities = curve.columns
        else:
            self.selected_maturities = selected_maturities

        if curve_m is None:
            self.curve_monthly = curve.resample('ME').mean()
        else:
            self.curve_monthly = curve_m

        self.t_d = self.curve.shape[0]
        self.t_m = self.curve_monthly.shape[0] - 1
        self.n = self.curve.shape[1]
        self.pc_factors_m, self.pc_factors_d, self.pc_loadings_m, self.pc_explained_m = self._get_pcs(self.curve_monthly, self.curve)

        self.rx_m = self._get_excess_returns()

        # ===== ACM Three-Step Regression =====
        # 1st Step - Factor VAR
        self.mu, self.phi, self.Sigma, self.v, self.s0 = self._estimate_var()

        # 2nd Step - Excess Returns
        self.beta, self.omega, self.beta_star = self._excess_return_regression()

        # 3rd Step - Convexity-adjusted price of risk
        self.lambda0, self.lambda1, self.mu_star, self.phi_star = self._retrieve_lambda()

        # Short Rate Equation
        self.delta0, self.delta1 = self._short_rate_equation(
            r1=self.curve_monthly.iloc[:, 0],
            X=self.pc_factors_m,
        )

        # Affine Yield Coefficients
        self.A, self.B = self._affine_coefficients(
            lambda0=self.lambda0,
            lambda1=self.lambda1,
        )

        # Risk-Neutral Coefficients
        self.Arn, self.Brn = self._affine_coefficients(
            lambda0=np.zeros(self.lambda0.shape),
            lambda1=np.zeros(self.lambda1.shape),
        )

        # Model Implied Yield
        self.miy = self._compute_yields(self.A, self.B)

        # Risk Neutral Yield
        self.rny = self._compute_yields(self.Arn, self.Brn)

        # Term Premium
        self.tp = self.miy - self.rny

        # Expected Return
        self.er_loadings, self.er_hist = self._expected_return()

    def forward_rates_ts(self, t1, t2):
        """
        Compute the time series of t1-to-t2 year forward yields and their
        decomposition into risk-neutral yield and term premium.

        The annualized forward rate from maturity m1 to m2 months is:
            f(t) = -(A_m2 - A_m1 + (B_m2 - B_m1)' X_t) / ((m2-m1)/12)

        Parameters
        ----------
        t1 : float
            Start of the forward horizon in years (e.g. 5 for the 5-year point).
        t2 : float
            End of the forward horizon in years (e.g. 10 for the 10-year point).

        Returns
        -------
        pd.DataFrame
            Daily time series with columns:
                miy — model-implied forward yield
                rny — risk-neutral forward yield
                tp  — forward term premium (miy - rny)
        """
        m1 = int(round(t1 * 12))
        m2 = int(round(t2 * 12))

        if m1 < 1 or m2 > self.n:
            raise ValueError(
                f"Forward horizon [{t1}, {t2}] years maps to months [{m1}, {m2}], "
                f"which is outside the curve range [1, {self.n}]."
            )

        span = (m2 - m1) / 12           # horizon length in years
        X_d = self.pc_factors_d.values  # T_d x K
        idx = self.pc_factors_d.index

        # A, B are 0-indexed: maturity n → index n-1
        dA    = self.A[m2 - 1]   - self.A[m1 - 1]
        dB    = self.B[m2 - 1]   - self.B[m1 - 1]
        dA_rn = self.Arn[m2 - 1] - self.Arn[m1 - 1]
        dB_rn = self.Brn[m2 - 1] - self.Brn[m1 - 1]

        miy = pd.Series(-(dA    + X_d @ dB)    / span, index=idx)
        rny = pd.Series(-(dA_rn + X_d @ dB_rn) / span, index=idx)

        return pd.DataFrame({"miy": miy, "rny": rny, "tp": miy - rny})

    def forward_rates_cs(self, date=None):
        """
        Compute the forward curves for a given date.

        Parameters
        ----------
        date : date-like
            date in any format that can be interpreted by pandas.to_datetime()
        """

        if date is None:
            date = self.curve.index[-1]

        date = pd.to_datetime(date)
        fwd_mkt = self._compute_fwd_curve(self.curve.loc[date])
        fwd_miy = self._compute_fwd_curve(self.miy.loc[date])
        fwd_rny = self._compute_fwd_curve(self.rny.loc[date])
        df = pd.concat(
            [
                fwd_mkt.rename("Observed"),
                fwd_miy.rename("Fitted"),
                fwd_rny.rename("Risk-Neutral"),
            ],
            axis=1,
        )
        return df

    @staticmethod
    def _compute_fwd_curve(curve):
        aux_curve = curve.reset_index(drop=True)
        aux_curve.index = aux_curve.index + 1
        factor = (1 + aux_curve) ** (aux_curve.index / 12)
        fwd_factor = factor / factor.shift(1).fillna(1)
        fwds = (fwd_factor ** 12) - 1
        fwds = pd.Series(fwds.values, index=curve.index)
        return fwds

    @staticmethod
    def _assertions(curve, curve_m, selected_maturities):
        # Selected maturities are available
        if selected_maturities is not None:
            assert all([col in curve.columns for col in selected_maturities]), \
                "not all `selected_columns` are available in `curve`"

        # Consecutive monthly maturities
        cond1 = curve.columns[0] != 1
        cond2 = not all(np.diff(curve.columns.values) == 1)
        if cond1 or cond2:
            msg = "`curve` columns must be consecutive integers starting from 1"
            raise AssertionError(msg)

        # Only if `curve_m` is passed
        if curve_m is not None:

            # Same columns
            assert curve_m.columns.equals(curve.columns), \
                "columns of `curve` and `curve_m` must be the same"

            # Monthly frequency
            assert pd.infer_freq(curve_m.index) == 'M', \
                "`curve_m` must have a DatetimeIndex with monthly frequency"

    def _get_excess_returns(self):
        ttm = np.arange(1, self.n + 1) / 12
        log_prices = - self.curve_monthly * ttm
        rf = - log_prices.iloc[:, 0].shift(1)
        rx = (log_prices - log_prices.shift(1, axis=0).shift(-1, axis=1)).subtract(rf, axis=0)
        rx = rx.shift(1, axis=1)

        rx = rx.dropna(how='all', axis=0)
        rx[1] = 0
        return rx

    def _get_pcs(self, curve_m, curve_d):

        # The authors' code shows that they ignore the first 2 maturities for
        # the PC estimation.
        curve_m_cut = curve_m.iloc[:, 2:]
        curve_d_cut = curve_d.iloc[:, 2:]

        mean_yields = curve_m_cut.mean()
        curve_m_cut = curve_m_cut - mean_yields
        curve_d_cut = curve_d_cut - mean_yields

        pca = PCA(n_components=self.n_factors)
        pca.fit(curve_m_cut)
        col_names = [f'PC {i + 1}' for i in range(self.n_factors)]
        df_loadings = pd.DataFrame(
            data=pca.components_.T,
            columns=col_names,
            index=curve_m_cut.columns,
        )

        df_pc_m = curve_m_cut @ df_loadings
        sigma_factor = df_pc_m.std()
        df_pc_m = df_pc_m / df_pc_m.std()
        df_loadings = df_loadings / sigma_factor

        # Enforce average positive loadings
        sign_changes = np.sign(df_loadings.mean())
        df_loadings = sign_changes * df_loadings
        df_pc_m = sign_changes * df_pc_m

        # Daily frequency
        df_pc_d = curve_d_cut @ df_loadings

        # Percent Explained
        df_explained = pd.Series(
            data=pca.explained_variance_ratio_,
            name='Explained Variance',
            index=col_names,
        )

        return df_pc_m, df_pc_d, df_loadings, df_explained

    def _estimate_var(self):
        X = self.pc_factors_m.copy().T
        X_lhs = X.values[:, 1:]  # X_t+1. Left hand side of VAR
        X_rhs = np.vstack((np.ones((1, self.t_m)), X.values[:, 0:-1]))  # X_t and a constant.

        var_coeffs = (X_lhs @ np.linalg.pinv(X_rhs))

        phi = var_coeffs[:, 1:]

        # Leave the estimated constant
        # mu = var_coeffs[:, [0]]

        # Force constant to zero
        mu = np.zeros((self.n_factors, 1))
        var_coeffs[:, [0]] = 0

        # Residuals
        v = X_lhs - var_coeffs @ X_rhs
        Sigma = v @ v.T / (self.t_m - 1)

        s0 = np.cov(v).reshape((-1, 1))

        return mu, phi, Sigma, v, s0

    def _excess_return_regression(self):

        if self.selected_maturities is not None:
            rx = self.rx_m[self.selected_maturities].values
        else:
            rx = self.rx_m.values

        X = self.pc_factors_m.copy().T.values[:, :-1]
        Z = np.vstack((np.ones((1, self.t_m)), X, self.v)).T  # Lagged X and Innovations
        abc = inv(Z.T @ Z) @ (Z.T @ rx)
        E = rx - Z @ abc
        omega = np.var(E.reshape(-1, 1)) * np.eye(len(self.selected_maturities))

        abc = abc.T
        beta = abc[:, -self.n_factors:]

        beta_star = np.zeros((len(self.selected_maturities), self.n_factors**2))

        for i in range(len(self.selected_maturities)):
            beta_star[i, :] = np.kron(beta[i, :], beta[i, :]).T

        return beta, omega, beta_star

    def _retrieve_lambda(self):
        rx = self.rx_m[self.selected_maturities]
        factors = np.hstack([np.ones((self.t_m, 1)), self.pc_factors_m.iloc[:-1].values])

        # Orthogonalize factors with respect to v
        v_proj = self.v.T @ np.linalg.pinv(self.v @ self.v.T) @ self.v
        factors = factors - v_proj @ factors

        adjustment = self.beta_star @ self.s0 + np.diag(self.omega).reshape(-1, 1)
        rx_adjusted = rx.values + (1 / 2) * np.tile(adjustment, (1, self.t_m)).T
        Y = (inv(factors.T @ factors) @ factors.T @ rx_adjusted).T

        # Compute Lambda
        X = self.beta
        Lambda = inv(X.T @ X) @ X.T @ Y
        lambda0 = Lambda[:, 0]
        lambda1 = Lambda[:, 1:]

        muStar = self.mu.reshape(-1) - lambda0
        phiStar = self.phi - lambda1

        return lambda0, lambda1, muStar, phiStar

    @staticmethod
    def _short_rate_equation(r1, X):
        r1 = r1 / 12
        X = add_constant(X)
        Delta = inv(X.T @ X) @ X.T @ r1
        delta0 = Delta.iloc[0]
        delta1 = Delta.iloc[1:].values
        return delta0, delta1

    def _affine_coefficients(self, lambda0, lambda1):
        lambda0 = lambda0.reshape(-1, 1)

        A = np.zeros(self.n)
        B = np.zeros((self.n, self.n_factors))

        A[0] = - self.delta0
        B[0, :] = - self.delta1

        for n in range(1, self.n):
            Bpb = np.kron(B[n - 1, :], B[n - 1, :])
            s0term = 0.5 * (Bpb @ self.s0 + self.omega[0, 0])

            A[n] = (A[n - 1] + B[n - 1, :] @ (self.mu - lambda0) + s0term + A[0])[0]
            B[n, :] = B[n - 1, :] @ (self.phi - lambda1) + B[0, :]

        return A, B

    def _compute_yields(self, A, B):
        A = A.reshape(-1, 1)
        multiplier = np.tile(self.curve.columns / 12, (self.t_d, 1)).T
        yields = (- ((np.tile(A, (1, self.t_d)) + B @ self.pc_factors_d.T) / multiplier).T).values
        yields = pd.DataFrame(
            data=yields,
            index=self.curve.index,
            columns=self.curve.columns,
        )
        return yields

    def _expected_return(self):
        """
        Compute the "expected return" and "convexity adjustment" terms, to get
        the expected return loadings and historical estimate

        Loadings are interpreted as the effect of 1sd of the PCs on the
        expected returns
        """
        stds = self.pc_factors_m.std().values[:, None].T
        er_loadings = (self.B @ self.lambda1) * stds
        er_loadings = pd.DataFrame(
            data=er_loadings,
            columns=self.pc_factors_m.columns,
            index=range(1, self.n + 1),
        )

        # Historical estimate
        exp_ret = (self.B @ (self.lambda1 @ self.pc_factors_d.T + self.lambda0.reshape(-1, 1))).values
        conv_adj = np.diag(self.B @ self.Sigma @ self.B.T) + self.omega[0, 0]
        er_hist = (exp_ret - 0.5 * conv_adj[:, None]).T
        er_hist_d = pd.DataFrame(
            data=er_hist,
            index=self.pc_factors_d.index,
            columns=self.curve.columns,
        )
        return er_loadings, er_hist_d


class RealACM:
    """
    Implements the joint Gaussian affine term structure model from:

        Abrahams, Michael, Tobias Adrian, Richard K. Crump, and Emanuel Moench.
        "Decomposing Real and Nominal Yield Curves." Journal of Monetary
        Economics 84 (2016): 182-200.

    Jointly prices nominal Treasury and TIPS yield curves. Decomposes
    breakeven inflation into expected inflation, inflation risk premium,
    and a liquidity component.

    The model uses K = K_N + K_R + 1 pricing factors:
        - K_N nominal principal components (from nominal Treasury yields)
        - K_R real principal components (from residuals of TIPS yields
          orthogonalized with respect to nominal PCs and the liquidity factor)
        - 1 liquidity factor (observable, passed by the user)

    Estimation follows the three-step regression approach (Section 3 of the
    paper), adapted from Adrian, Crump, and Moench (2013).

    Attributes
    ----------
    n_factors_n : int
        Number of nominal principal components.

    n_factors_r : int
        Number of real principal components.

    n_factors : int
        Total number of pricing factors (K_N + K_R + 1).

    curve : pd.DataFrame
        Daily nominal zero-coupon log-yields.

    real_curve : pd.DataFrame
        Daily TIPS zero-coupon log-yields.

    liquidity : pd.Series
        Daily liquidity factor.

    cpi : pd.Series
        Monthly CPI index used to compute realized inflation.

    curve_monthly : pd.DataFrame
        Monthly nominal yields (resampled or passed directly).

    tips_curve_monthly : pd.DataFrame
        Monthly TIPS yields (resampled or passed directly).

    liquidity_monthly : pd.Series
        Monthly liquidity factor (resampled).

    inflation_monthly : pd.Series
        Monthly log inflation: log(CPI_t / CPI_{t-1}).

    t_m : int
        Number of monthly time observations used in estimation.

    t_d : int
        Number of daily time observations.

    n_n : int
        Number of nominal maturity columns.

    n_r : int
        Number of TIPS maturity columns.

    pc_factors_m : pd.DataFrame
        All K pricing factors at monthly frequency.

    pc_factors_d : pd.DataFrame
        All K pricing factors at daily frequency.

    pc_loadings_nom : pd.DataFrame
        Nominal yield PC loadings.

    pc_loadings_real : pd.DataFrame
        Real yield residual PC loadings.

    rx_n_m : pd.DataFrame
        Nominal excess returns at monthly frequency.

    rx_r_m : pd.DataFrame
        Inflation-adjusted real excess returns (rx_R + pi) at monthly frequency.

    mu_X : np.ndarray
        Sample mean of the pricing factors (K x 1).

    phi : np.ndarray
        VAR(1) slope matrix under the physical measure (K x K).

    Sigma : np.ndarray
        Covariance matrix of VAR innovations (K x K).

    v : np.ndarray
        VAR residuals (K x T_m).

    mu_star : np.ndarray
        Risk-neutral drift (K x 1): mu_star = (I-Phi) mu_X - lambda0.

    phi_star : np.ndarray
        Risk-neutral AR matrix (K x K): phi_star = Phi - lambda1.

    lambda0 : np.ndarray
        Constant price of risk (K,).

    lambda1 : np.ndarray
        Time-varying price of risk loadings (K x K).

    delta0 : float
        Nominal short rate equation intercept.

    delta1 : np.ndarray
        Nominal short rate equation slope (K,).

    pi0 : float
        Scalar intercept of the one-period log inflation equation.

    pi1 : np.ndarray
        Slope of the one-period log inflation equation (K,).

    A_n, B_n : np.ndarray
        Nominal affine pricing coefficients (model-implied / physical measure).

    A_rn_n, B_rn_n : np.ndarray
        Nominal affine pricing coefficients (risk-neutral measure).

    A_r, B_r : np.ndarray
        Real affine pricing coefficients (model-implied).

    A_rn_r, B_rn_r : np.ndarray
        Real affine pricing coefficients (risk-neutral).

    miy_n : pd.DataFrame
        Nominal model-implied yields.

    rny_n : pd.DataFrame
        Nominal risk-neutral yields.

    tp_n : pd.DataFrame
        Nominal term premium (miy_n - rny_n).

    miy_r : pd.DataFrame
        Real model-implied yields.

    rny_r : pd.DataFrame
        Real risk-neutral yields.

    tp_r : pd.DataFrame
        Real term premium (miy_r - rny_r).

    breakeven : pd.DataFrame
        Model-implied breakeven inflation (miy_n - miy_r).

    irp : pd.DataFrame
        Inflation risk premium (tp_n - tp_r).
    """

    def __init__(
            self,
            nominal_curve,
            real_curve,
            liquidity,
            cpi,
            n_factors_n=3,
            n_factors_r=2,
            nominal_curve_m=None,
            tips_curve_m=None,
            selected_maturities_n=None,
            selected_maturities_r=None,
    ):
        """
        Parameters
        ----------
        nominal_curve : pd.DataFrame
            Annualized log-yields for nominal zero-coupon bonds. Columns must
            be consecutive integers starting from 1 (monthly maturities).
            Index must be a DatetimeIndex.

        real_curve : pd.DataFrame
            Annualized log-yields for real (TIPS) zero-coupon bonds. Columns
            must be consecutive integers (monthly maturities, typically 24+).
            Index must be a DatetimeIndex.

        liquidity : pd.Series
            Observable liquidity factor. Must be a positive series with a
            DatetimeIndex aligned with nominal_curve.

        cpi : pd.Series
            Monthly CPI index used to compute realized inflation. Must have a
            DatetimeIndex at monthly frequency.

        n_factors_n : int
            Number of nominal principal components (default 3).

        n_factors_r : int
            Number of real (orthogonalized) principal components (default 2).

        nominal_curve_m : pd.DataFrame, optional
            Monthly nominal yields for parameter estimation. If None, the
            daily nominal_curve is resampled.

        tips_curve_m : pd.DataFrame, optional
            Monthly TIPS yields for parameter estimation. If None, the
            daily tips_curve is resampled.

        selected_maturities_n : list of int, optional
            Nominal maturities to include in the SUR return regression.
            If None, all maturities are used.

        selected_maturities_r : list of int, optional
            Real maturities to include in the SUR return regression and
            in the pi0/pi1 optimization. If None, all TIPS maturities are used.
        """
        self._assertions(
            nominal_curve,
            real_curve,
            nominal_curve_m,
            tips_curve_m,
            selected_maturities_n,
            selected_maturities_r,
        )

        self.n_factors_n = n_factors_n
        self.n_factors_r = n_factors_r
        self.n_factors = n_factors_n + n_factors_r + 1  # +1 for liquidity, could add more in the future

        self.curve = nominal_curve
        self.real_curve = real_curve
        self.liquidity = liquidity
        self.cpi = cpi

        self.n_n = nominal_curve.shape[1]
        self.n_r = real_curve.shape[1]
        self.t_d = nominal_curve.shape[0]

        if selected_maturities_n is None:
            self.selected_maturities_n = nominal_curve.columns.tolist()
        else:
            self.selected_maturities_n = selected_maturities_n

        if selected_maturities_r is None:
            self.selected_maturities_r = real_curve.columns.tolist()
        else:
            self.selected_maturities_r = selected_maturities_r

        # Monthly data
        if nominal_curve_m is None:
            self.curve_monthly = nominal_curve.resample('ME').mean()
        else:
            self.curve_monthly = nominal_curve_m

        if tips_curve_m is None:
            self.tips_curve_monthly = real_curve.resample('ME').mean()
        else:
            self.tips_curve_monthly = tips_curve_m

        self.liquidity_monthly = liquidity.resample('ME').mean()

        # Monthly log inflation: pi_t = log(CPI_t / CPI_{t-1})
        # CPI may have start-of-month dates; shift index to end-of-month to
        # align with the yield curve monthly index.
        pi_raw = np.log(cpi / cpi.shift(1)).dropna()
        pi_raw.index = pi_raw.index + pd.offsets.MonthEnd(0)
        self.inflation_monthly = pi_raw

        self.t_m = self.curve_monthly.shape[0] - 1

        # ===== Factor Construction =====
        (self.pc_factors_m,
         self.pc_factors_d,
         self.pc_loadings_nom,
         self.pc_loadings_real,
         self.pc_explained_nom,
         self.pc_explained_real) = self._get_pcs()

        # ===== Excess Returns =====
        self.rx_n_m = self._get_nominal_excess_returns()
        self.rx_r_m = self._get_real_returns()

        # ===== Step 1: VAR on all factors =====
        self.mu_X, self.phi, self.Sigma, self.v, self.s0 = self._estimate_var()

        # ===== Step 2: Stacked SUR =====
        self.phi_star, self.mu_star, self.B_gls, self.alpha_gls = self._stacked_sur()

        # ===== Step 3: Prices of Risk =====
        self.lambda0, self.lambda1 = self._retrieve_lambda()

        # ===== Short Rate Equation =====
        self.delta0, self.delta1 = NominalACM._short_rate_equation(
            r1=self.curve_monthly.iloc[:, 0],
            X=self.pc_factors_m,
        )

        # ===== Nominal Affine Coefficients =====
        self.A_n, self.B_n = self._nominal_affine_coefficients(
            lambda0=self.lambda0,
            lambda1=self.lambda1,
        )
        self.A_rn_n, self.B_rn_n = self._nominal_affine_coefficients(
            lambda0=np.zeros_like(self.lambda0),
            lambda1=np.zeros_like(self.lambda1),
        )

        # ===== Inflation Parameters (nonlinear optimization) =====
        self.pi0, self.pi1 = self._estimate_pi()

        # ===== Real Affine Coefficients =====
        self.A_r, self.B_r = self._real_affine_coefficients(
            pi0=self.pi0,
            pi1=self.pi1,
            phi_tilde=self.phi_star,
            mu_tilde=self.mu_star,
        )
        self.A_rn_r, self.B_rn_r = self._real_affine_coefficients(
            pi0=self.pi0,
            pi1=self.pi1,
            phi_tilde=self.phi,
            mu_tilde=(np.eye(self.n_factors) - self.phi) @ self.mu_X,
        )

        # ===== Model-Implied Yields =====
        self.miy_n = self._compute_yields(self.A_n, self.B_n, self.curve.columns)
        self.rny_n = self._compute_yields(self.A_rn_n, self.B_rn_n, self.curve.columns)
        self.tp_n = self.miy_n - self.rny_n

        tips_cols = self.real_curve.columns
        self.miy_r = self._compute_yields(self.A_r, self.B_r, tips_cols)
        self.rny_r = self._compute_yields(self.A_rn_r, self.B_rn_r, tips_cols)
        self.tp_r = self.miy_r - self.rny_r

        # ===== Breakeven and Inflation Risk Premium =====
        self.breakeven = self.miy_n[tips_cols] - self.miy_r
        self.irp = self.tp_n[tips_cols] - self.tp_r

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def forward_rates_ts(self, t1, t2):
        """
        Compute the time series of t1-to-t2 year forward yields and their
        decomposition into risk-neutral yields, term premia, and liquidity
        components for both the nominal and real curves.

        The annualized forward rate from maturity m1 to m2 months is:
            f(t) = -(A_m2 - A_m1 + (B_m2 - B_m1)' X_t) / ((m2-m1)/12)

        Parameters
        ----------
        t1 : float
            Start of the forward horizon in years (e.g. 5 for the 5-year point).
        t2 : float
            End of the forward horizon in years (e.g. 10 for the 10-year point).

        Returns
        -------
        pd.DataFrame
            Daily time series with columns:
                miy_n    — nominal model-implied forward yield
                rny_n    — nominal risk-neutral forward yield
                tp_n     — nominal forward term premium (miy_n - rny_n)
                liq_n    — liquidity component of the nominal forward yield
                miy_r    — real model-implied forward yield
                rny_r    — real risk-neutral forward yield
                tp_r     — real forward term premium (miy_r - rny_r)
                liq_r    — liquidity component of the real forward yield
                breakeven      — forward breakeven inflation (miy_n - miy_r)
                liq_adj_be     — liquidity-adjusted breakeven (breakeven - liq_r)
                irp            — inflation risk premium (tp_n - tp_r)
                exp_inflation  — expected inflation under RN measure
                                 (liq_adj_be - irp)
        """
        m1 = int(round(t1 * 12))
        m2 = int(round(t2 * 12))

        if m1 < 1 or m2 > self.n_n:
            raise ValueError(
                f"Forward horizon [{t1}, {t2}] years maps to months [{m1}, {m2}], "
                f"which is outside the nominal curve range [1, {self.n_n}]."
            )
        tips_cols = self.real_curve.columns.tolist()
        if m1 not in tips_cols or m2 not in tips_cols:
            raise ValueError(
                f"Forward horizon [{t1}, {t2}] years maps to months [{m1}, {m2}], "
                f"but TIPS maturities available are {tips_cols[0]}–{tips_cols[-1]}."
            )

        span = (m2 - m1) / 12          # horizon length in years
        X_d = self.pc_factors_d.values  # T_d x K
        idx = self.pc_factors_d.index
        liq_idx = self.n_factors - 1    # liquidity is the last factor

        # --- Nominal affine coefficients (0-indexed: maturity n → index n-1) ---
        dA_n   = self.A_n[m2 - 1]    - self.A_n[m1 - 1]
        dB_n   = self.B_n[m2 - 1]    - self.B_n[m1 - 1]
        dA_rn  = self.A_rn_n[m2 - 1] - self.A_rn_n[m1 - 1]
        dB_rn  = self.B_rn_n[m2 - 1] - self.B_rn_n[m1 - 1]

        miy_n = pd.Series(-(dA_n  + X_d @ dB_n)  / span, index=idx)
        rny_n = pd.Series(-(dA_rn + X_d @ dB_rn) / span, index=idx)
        tp_n  = miy_n - rny_n
        liq_n = pd.Series(-dB_n[liq_idx] * X_d[:, liq_idx] / span, index=idx)

        # --- Real affine coefficients (indexed by tips_curve.columns order) ---
        ir1 = tips_cols.index(m1)
        ir2 = tips_cols.index(m2)

        dA_r    = self.A_r[ir2]     - self.A_r[ir1]
        dB_r    = self.B_r[ir2]     - self.B_r[ir1]
        dA_rn_r = self.A_rn_r[ir2]  - self.A_rn_r[ir1]
        dB_rn_r = self.B_rn_r[ir2]  - self.B_rn_r[ir1]

        miy_r = pd.Series(-(dA_r    + X_d @ dB_r)    / span, index=idx)
        rny_r = pd.Series(-(dA_rn_r + X_d @ dB_rn_r) / span, index=idx)
        tp_r  = miy_r - rny_r
        liq_r = pd.Series(-dB_r[liq_idx] * X_d[:, liq_idx] / span, index=idx)

        breakeven     = miy_n - miy_r
        irp           = tp_n  - tp_r
        liq_adj_be    = breakeven - liq_r
        exp_inflation = liq_adj_be - irp

        return pd.DataFrame({
            "miy_n":         miy_n,
            "rny_n":         rny_n,
            "tp_n":          tp_n,
            "liq_n":         liq_n,
            "miy_r":         miy_r,
            "rny_r":         rny_r,
            "tp_r":          tp_r,
            "liq_r":         liq_r,
            "breakeven":     breakeven,
            "liq_adj_be":    liq_adj_be,
            "irp":           irp,
            "exp_inflation": exp_inflation,
        })

    def forward_rates_cs(self, date=None):
        """
        Compute the cross-sectional forward curves at a given date for both
        the nominal and real yield curves, together with all derived
        decomposition series (term premia, liquidity, breakeven, IRP,
        expected inflation).

        For each curve the forward rate at maturity n is the 1-month rate
        implied by holding a zero-coupon bond from n-1 to n months.

        Parameters
        ----------
        date : date-like, optional
            Date in any format interpretable by pandas.to_datetime(). Defaults
            to the last available date in the daily factor series.

        Returns
        -------
        dict with three keys:

        ``"nominal"`` : pd.DataFrame, indexed by maturity (months 1–N_N)
            Observed, Fitted, Risk-Neutral, Term Premium, Liquidity

        ``"real"`` : pd.DataFrame, indexed by TIPS maturities
            Observed, Fitted, Risk-Neutral, Term Premium, Liquidity

        ``"breakeven"`` : pd.DataFrame, indexed by TIPS maturities
            Breakeven, IRP, Liq-Adj Breakeven, Expected Inflation
        """
        if date is None:
            date = self.pc_factors_d.index[-1]
        date = pd.to_datetime(date)

        _fwd = NominalACM._compute_fwd_curve
        K = self.n_factors
        tips_cols = self.real_curve.columns

        # Liquidity factor value at this date (last factor in the state vector)
        X_liq = float(self.pc_factors_d.loc[date].iloc[-1])

        # Liquidity component of the nominal spot yield curve:
        #   liq_n = -(B_n[:, K-1] * X_liq) / (maturity / 12)
        # Convert to a forward curve via _compute_fwd_curve.
        mats_n = np.arange(1, self.n_n + 1)
        liq_yield_n = pd.Series(
            -(self.B_n[:, K - 1] * X_liq) / (mats_n / 12), index=mats_n
        )

        # Same for the real spot yield curve (TIPS maturities)
        tips_mats = tips_cols.values
        liq_yield_r = pd.Series(
            -(self.B_r[:, K - 1] * X_liq) / (tips_mats / 12), index=tips_cols
        )

        # --- Nominal forward curves ---
        fwd_nom_obs = _fwd(self.curve.loc[date])
        fwd_nom_fit = _fwd(self.miy_n.loc[date])
        fwd_nom_rn  = _fwd(self.rny_n.loc[date])
        fwd_liq_n   = _fwd(liq_yield_n)

        nominal = pd.DataFrame({
            "Observed":     fwd_nom_obs,
            "Fitted":       fwd_nom_fit,
            "Risk-Neutral": fwd_nom_rn,
            "Term Premium": fwd_nom_fit - fwd_nom_rn,
            "Liquidity":    fwd_liq_n,
        })

        # --- Real forward curves ---
        fwd_real_obs = _fwd(self.real_curve.loc[date])
        fwd_real_fit = _fwd(self.miy_r.loc[date])
        fwd_real_rn  = _fwd(self.rny_r.loc[date])
        fwd_liq_r    = _fwd(liq_yield_r)

        real = pd.DataFrame({
            "Observed":     fwd_real_obs,
            "Fitted":       fwd_real_fit,
            "Risk-Neutral": fwd_real_rn,
            "Term Premium": fwd_real_fit - fwd_real_rn,
            "Liquidity":    fwd_liq_r,
        })

        # --- Breakeven decomposition (at TIPS maturities) ---
        nom_fit_at_tips = fwd_nom_fit.loc[tips_cols]
        nom_tp_at_tips  = nominal["Term Premium"].loc[tips_cols]

        breakeven      = nom_fit_at_tips.values - fwd_real_fit.values
        irp            = nom_tp_at_tips.values  - real["Term Premium"].values
        liq_adj_be     = breakeven - fwd_liq_r.values
        exp_inflation  = liq_adj_be - irp

        breakeven_df = pd.DataFrame({
            "Breakeven":        breakeven,
            "IRP":              irp,
            "Liq-Adj Breakeven": liq_adj_be,
            "Expected Inflation": exp_inflation,
        }, index=tips_cols)

        return {"nominal": nominal, "real": real, "breakeven": breakeven_df}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _assertions(nominal_curve, tips_curve, nominal_curve_m, tips_curve_m,
                    selected_maturities_n, selected_maturities_r):
        # Nominal curve: consecutive integers starting at 1
        cond1 = nominal_curve.columns[0] != 1
        cond2 = not all(np.diff(nominal_curve.columns.values) == 1)
        if cond1 or cond2:
            raise AssertionError("`nominal_curve` columns must be consecutive integers starting from 1")

        # TIPS curve: consecutive integers
        if not all(np.diff(tips_curve.columns.values) == 1):
            raise AssertionError("`tips_curve` columns must be consecutive integers")

        if selected_maturities_n is not None:
            assert all(m in nominal_curve.columns for m in selected_maturities_n), \
                "not all `selected_maturities_n` are in `nominal_curve`"

        if selected_maturities_r is not None:
            assert all(m in tips_curve.columns for m in selected_maturities_r), \
                "not all `selected_maturities_r` are in `tips_curve`"

        if nominal_curve_m is not None:
            assert nominal_curve_m.columns.equals(nominal_curve.columns), \
                "columns of `nominal_curve` and `nominal_curve_m` must match"
            assert pd.infer_freq(nominal_curve_m.index) == 'M', \
                "`nominal_curve_m` must have monthly frequency"

        if tips_curve_m is not None:
            assert tips_curve_m.columns.equals(tips_curve.columns), \
                "columns of `tips_curve` and `tips_curve_m` must match"

    def _get_pcs(self):
        """
        Build the K pricing factors:
          1. K_N nominal PCs from demeaned nominal yields (skip first 2 maturities)
          2. K_R real PCs from residuals of TIPS yields regressed on nominal PCs
             and the liquidity factor
          3. Liquidity factor (standardized)
        Returns monthly and daily factor DataFrames plus loading matrices.
        """
        # --- Nominal PCs (same logic as NominalACM) ---
        nom_m = self.curve_monthly.iloc[:, 2:]   # skip first 2 maturities
        nom_d = self.curve.iloc[:, 2:]
        mean_nom = nom_m.mean()
        nom_m_dm = nom_m - mean_nom
        nom_d_dm = nom_d - mean_nom

        pca_nom = PCA(n_components=self.n_factors_n)
        pca_nom.fit(nom_m_dm)
        col_names_n = [f'Nom PC {i+1}' for i in range(self.n_factors_n)]
        loadings_nom = pd.DataFrame(
            data=pca_nom.components_.T,
            columns=col_names_n,
            index=nom_m_dm.columns,
        )
        nom_pc_m = nom_m_dm @ loadings_nom
        sigma_nom = nom_pc_m.std()
        nom_pc_m = nom_pc_m / sigma_nom
        loadings_nom = loadings_nom / sigma_nom

        # Enforce positive average loadings
        sign_n = np.sign(loadings_nom.mean())
        loadings_nom = sign_n * loadings_nom
        nom_pc_m = sign_n * nom_pc_m

        nom_pc_d = nom_d_dm @ loadings_nom

        explained_nom = pd.Series(
            data=pca_nom.explained_variance_ratio_,
            index=col_names_n,
            name='Explained Variance',
        )

        # --- Align liquidity to monthly ---
        liq_m = self.liquidity_monthly.reindex(self.curve_monthly.index, method='ffill')
        liq_d = self.liquidity.reindex(self.curve.index, method='ffill')

        # --- Orthogonalize TIPS yields w.r.t. nominal PCs and liquidity ---
        # Align TIPS monthly to nominal monthly index
        tips_m = self.tips_curve_monthly.reindex(self.curve_monthly.index, method='ffill')

        # Regression: tips_yield ~ nom_PCs + liquidity (equation by equation, monthly)
        regressors_m = pd.concat([nom_pc_m, liq_m.rename('liquidity')], axis=1).dropna()
        tips_align = tips_m.reindex(regressors_m.index)

        lr = LinearRegression(fit_intercept=True)
        lr.fit(regressors_m.values, tips_align.values)
        tips_resid = tips_align.values - lr.predict(regressors_m.values)
        tips_resid_df = pd.DataFrame(
            data=tips_resid,
            index=regressors_m.index,
            columns=tips_align.columns,
        )

        # --- Real PCs from TIPS residuals ---
        pca_real = PCA(n_components=self.n_factors_r)
        pca_real.fit(tips_resid_df.values)
        col_names_r = [f'Real PC {i+1}' for i in range(self.n_factors_r)]
        loadings_real = pd.DataFrame(
            data=pca_real.components_.T,
            columns=col_names_r,
            index=tips_resid_df.columns,
        )
        real_pc_m = tips_resid_df @ loadings_real
        sigma_real = real_pc_m.std()
        real_pc_m = real_pc_m / sigma_real
        loadings_real = loadings_real / sigma_real

        # Enforce positive average loadings
        sign_r = np.sign(loadings_real.mean())
        loadings_real = sign_r * loadings_real
        real_pc_m = sign_r * real_pc_m

        # Daily real PCs: compute TIPS daily residuals then project
        tips_d = self.real_curve.reindex(self.curve.index, method='ffill')
        regressors_d = pd.concat([nom_pc_d, liq_d.rename('liquidity')], axis=1)
        # use monthly-fitted regression coefficients to get daily residuals
        tips_d_pred = lr.predict(regressors_d.reindex(tips_d.index).values)
        tips_resid_d = tips_d.values - tips_d_pred
        tips_resid_d_df = pd.DataFrame(
            data=tips_resid_d,
            index=tips_d.index,
            columns=tips_d.columns,
        )
        real_pc_d = tips_resid_d_df @ loadings_real

        explained_real = pd.Series(
            data=pca_real.explained_variance_ratio_,
            index=col_names_r,
            name='Explained Variance',
        )

        # --- Standardize and include liquidity factor ---
        liq_std = (liq_m - liq_m.mean()) / liq_m.std()
        liq_d_std = (liq_d - liq_m.mean()) / liq_m.std()

        # --- Stack all K factors ---
        pc_m = pd.concat([
            nom_pc_m,
            real_pc_m.reindex(nom_pc_m.index),
            liq_std.reindex(nom_pc_m.index).rename('Liquidity'),
        ], axis=1).dropna()

        pc_d = pd.concat([
            nom_pc_d,
            real_pc_d.reindex(nom_pc_d.index),
            liq_d_std.reindex(nom_pc_d.index).rename('Liquidity'),
        ], axis=1).ffill().dropna()

        return pc_m, pc_d, loadings_nom, loadings_real, explained_nom, explained_real

    def _get_nominal_excess_returns(self):
        """Nominal log excess returns at monthly frequency (same as NominalACM)."""
        curve_m = self.curve_monthly.reindex(self.pc_factors_m.index.union(
            [self.pc_factors_m.index[0] - pd.offsets.MonthEnd(1)]))
        ttm = np.arange(1, self.n_n + 1) / 12
        log_prices = -self.curve_monthly * ttm
        rf = -log_prices.iloc[:, 0].shift(1)
        rx = (log_prices - log_prices.shift(1, axis=0).shift(-1, axis=1)).subtract(rf, axis=0)
        rx = rx.shift(1, axis=1)
        rx = rx.dropna(how='all', axis=0)
        rx[1] = 0
        return rx

    def _get_real_returns(self):
        """
        Inflation-adjusted real log excess returns: rx_{R,t+1} + pi_{t+1}.
        This adds realized monthly log inflation to the real excess return,
        which simplifies to log(P_{R,t+1}^{n-1}) - log(P_{R,t}^n) - r_t + pi_{t+1}.
        """
        tips_m = self.tips_curve_monthly
        mats_r = tips_m.columns
        ttm = mats_r.values / 12
        log_prices_r = -tips_m * ttm

        # Risk-free rate: 1-month nominal yield / 12
        rf = self.curve_monthly.iloc[:, 0] / 12

        # Real excess return for n-period bond: hold for 1 month, bond becomes n-1 period
        # rx_R,t+1 = log P_{R,t+1}^{n-1} - log P_{R,t}^n - r_t
        rx_r = (log_prices_r - log_prices_r.shift(1, axis=0).shift(-1, axis=1)
                ).subtract(rf, axis=0)
        rx_r = rx_r.shift(1, axis=1)  # shift so maturity n uses n-1 bond next period

        # Add realized monthly log inflation pi_{t+1}
        pi_monthly = self.inflation_monthly
        rx_r_plus_pi = rx_r.add(pi_monthly, axis=0)

        # Align to factor index
        idx = self.pc_factors_m.index
        rx_r_plus_pi = rx_r_plus_pi.reindex(idx).dropna(how='all')

        # The shortest TIPS maturity has no predecessor -> set to 0 or drop
        # (analogous to rx[1] = 0 for nominal, but TIPS start at 24)
        first_col = mats_r[0]
        rx_r_plus_pi[first_col] = 0

        return rx_r_plus_pi

    def _estimate_var(self):
        """VAR(1) on the full K-factor vector X_t. Same structure as NominalACM."""
        X = self.pc_factors_m.T
        T = X.shape[1]
        X_lhs = X.values[:, 1:]    # X_{t+1}
        X_rhs = np.vstack((np.ones((1, T - 1)), X.values[:, :-1]))  # [1; X_t]

        var_coeffs = X_lhs @ np.linalg.pinv(X_rhs)
        phi = var_coeffs[:, 1:]

        # Force intercept to zero (as in NominalACM)
        mu_X = np.zeros((self.n_factors, 1))
        var_coeffs[:, [0]] = 0

        v = X_lhs - var_coeffs @ X_rhs
        Sigma = v @ v.T / (T - 2)
        s0 = np.cov(v).reshape((-1, 1))

        return mu_X, phi, Sigma, v, s0

    def _stacked_sur(self):
        """
        Two-step GLS SUR regression on stacked nominal and real returns.

        Model: R_{t+1} = alpha * 1' - B * Phi_tilde * X_t + B * X_{t+1} + E

        Step 1 (OLS): regress R on [1, X_{t-1}, X_t] -> (alpha_OLS, -B*Phi_tilde_OLS, B_OLS)
        Step 2 (GLS): use Sigma_e to refine Phi_tilde, then re-run SUR.
        Returns phi_star (= Phi_tilde), mu_star (= mu_tilde), B_gls, alpha_gls.
        """
        # Align returns to a common monthly index
        idx = self.pc_factors_m.index
        rx_n = self.rx_n_m[self.selected_maturities_n].reindex(idx).dropna(how='all')
        rx_r = self.rx_r_m[self.selected_maturities_r].reindex(idx).dropna(how='all')

        common_idx = rx_n.index.intersection(rx_r.index)
        rx_n = rx_n.reindex(common_idx)
        rx_r = rx_r.reindex(common_idx)
        X_m = self.pc_factors_m.reindex(common_idx)

        T = len(common_idx)
        N_N = len(self.selected_maturities_n)
        N_R = len(self.selected_maturities_r)
        N = N_N + N_R
        K = self.n_factors

        # R: (T x N), rows = time, cols = assets
        R = np.hstack([rx_n.values, rx_r.values])  # T x N

        # X_{t-1} and X_t (shifted by 1)
        X_lag = X_m.iloc[:-1].values   # T-1 x K  (X_{t-1})
        X_cur = X_m.iloc[1:].values    # T-1 x K  (X_t)
        R_reg = R[1:]                  # T-1 x N  (R_t+1, matching X_t)

        T_reg = T - 1
        ones = np.ones((T_reg, 1))

        # OLS regressor: [1, X_{t-1}, X_t]  (T_reg x (1 + 2K))
        Z = np.hstack([ones, X_lag, X_cur])  # T_reg x (1+2K)

        # OLS: coeffs shape (1+2K) x N
        ZtZ_inv = inv(Z.T @ Z)
        coeffs_ols = ZtZ_inv @ (Z.T @ R_reg)  # (1+2K) x N

        # Parse: alpha_OLS (1xN), -B*Phi_tilde_OLS (KxN), B_OLS (KxN)
        alpha_ols = coeffs_ols[0:1, :]         # 1 x N
        neg_BPhi_ols = coeffs_ols[1:1+K, :].T  # N x K
        B_ols = coeffs_ols[1+K:, :].T           # N x K

        # Residuals and Sigma_e
        E_ols = R_reg - Z @ coeffs_ols          # T_reg x N
        Sigma_e = E_ols.T @ E_ols / T_reg       # N x N

        # Stabilize Sigma_e
        Sigma_e = Sigma_e + 1e-8 * np.eye(N)
        Sigma_e_inv = inv(Sigma_e)

        # GLS estimate of Phi_tilde:
        # Phi_tilde_GLS = -(B_OLS' Sigma_e^{-1} B_OLS)^{-1} B_OLS' Sigma_e^{-1} (B*Phi_tilde_OLS)
        # neg_BPhi_ols = -B * Phi_tilde_OLS  =>  B*Phi_tilde_OLS = -neg_BPhi_ols
        B_Phi_ols = -neg_BPhi_ols  # N x K

        BtSiB = B_ols.T @ Sigma_e_inv @ B_ols   # K x K
        # B_Phi_ols = -C_lag  (the theoretical B*Phi_tilde = negative of OLS coeff on X_lag)
        # GLS: Phi_tilde = (B' Se^{-1} B)^{-1} B' Se^{-1} B_Phi_ols
        #                = -inv(B'Se^{-1}B) @ B'Se^{-1} C_lag  (as in the paper)
        BtSiBPhi = B_ols.T @ Sigma_e_inv @ B_Phi_ols  # K x K
        phi_tilde_gls = inv(BtSiB) @ BtSiBPhi  # K x K

        # GLS pass: regress R on [1, (-Phi_tilde_GLS * X_{t-1} + X_t)]
        X_gls = X_cur - X_lag @ phi_tilde_gls.T  # T_reg x K  (= -Phi_tilde*X_lag + X_cur)
        Z2 = np.hstack([ones, X_gls])            # T_reg x (1+K)

        # GLS regression: minimize (R - Z2 @ C)' Sigma_e^{-1} (R - Z2 @ C)
        # Solution: C = (Z2' Sigma_e^{-1} Z2)^{-1} Z2' Sigma_e^{-1} R
        # Since Sigma_e is the same for all time periods, this reduces to OLS per-equation
        # with a GLS twist. We use equation-by-equation OLS (which is efficient for SUR
        # when regressors are the same across equations).
        Z2tZ2_inv = inv(Z2.T @ Z2)
        coeffs_gls = Z2tZ2_inv @ (Z2.T @ R_reg)  # (1+K) x N

        alpha_gls = coeffs_gls[0:1, :]    # 1 x N
        B_gls = coeffs_gls[1:, :].T       # N x K

        # Estimate mu_tilde from alpha_gls = -B_gls * mu_tilde - 0.5 * gamma
        # gamma_i = B_i' Sigma B_i for each asset i (convexity adjustment)
        gamma = np.array([B_gls[i] @ self.Sigma @ B_gls[i] for i in range(N)])  # N,

        # alpha_gls = -B_gls * mu_tilde - 0.5 * gamma
        # => B_gls * mu_tilde = -alpha_gls - 0.5 * gamma
        rhs = (-alpha_gls.flatten() - 0.5 * gamma)  # N,
        # Least squares: mu_tilde = (B_gls' B_gls)^{-1} B_gls' rhs
        mu_tilde = inv(B_gls.T @ B_gls) @ (B_gls.T @ rhs)  # K,

        return phi_tilde_gls, mu_tilde.reshape(-1, 1), B_gls, alpha_gls

    def _retrieve_lambda(self):
        """Recover prices of risk from physical and risk-neutral parameters."""
        lambda0 = ((np.eye(self.n_factors) - self.phi) @ self.mu_X
                   - self.mu_star).flatten()
        lambda1 = self.phi - self.phi_star
        return lambda0, lambda1

    def _nominal_affine_coefficients(self, lambda0, lambda1):
        """
        Nominal affine recursion (same structure as NominalACM._affine_coefficients).
        A_0 = -delta0, B_0 = -delta1
        A_n = A_{n-1} + B_{n-1}' mu_tilde + 0.5 * B_{n-1}' Sigma B_{n-1} - delta0
        B_n' = B_{n-1}' Phi_tilde - delta1'
        where mu_tilde = mu_star + lambda0 (for RN: mu_tilde = mu_X*(I-phi) = physical drift)
        and Phi_tilde = phi_star + lambda1 (for RN: phi)
        """
        lambda0 = lambda0.flatten()
        # mu_tilde = mu_X - lambda0; mu_X is forced to 0 in _estimate_var
        mu_tilde = self.mu_X.flatten() - lambda0
        phi_tilde = self.phi - lambda1

        A = np.zeros(self.n_n)
        B = np.zeros((self.n_n, self.n_factors))

        A[0] = -self.delta0
        B[0, :] = -self.delta1

        for n in range(1, self.n_n):
            b = B[n-1, :]
            A[n] = float(A[n-1] + b @ mu_tilde + 0.5 * b @ self.Sigma @ b + A[0])
            B[n, :] = b @ phi_tilde + B[0, :]

        return A, B

    def _real_affine_coefficients(self, pi0, pi1, phi_tilde, mu_tilde):
        """
        Real affine recursion (equations 17-18 from the paper):
        A_{R,0} = 0, B_{R,0} = 0
        B_{R,n}' = (B_{R,n-1} + pi1)' * Phi_tilde - delta1'
        A_{R,n} = A_{R,n-1} + (B_{R,n-1} + pi1)' * mu_tilde
                  + 0.5 * (B_{R,n-1} + pi1)' * Sigma * (B_{R,n-1} + pi1) - delta0
        where delta0_R = delta0 - pi0.
        """
        pi1 = np.asarray(pi1).flatten()
        if isinstance(mu_tilde, np.ndarray) and mu_tilde.ndim == 2:
            mu_tilde = mu_tilde.flatten()

        delta0_R = self.delta0 - pi0

        # TIPS columns are not necessarily 1-indexed; we compute for all TIPS maturities
        n_max = int(self.real_curve.columns.max())

        A_all = np.zeros(n_max + 1)
        B_all = np.zeros((n_max + 1, self.n_factors))

        for n in range(1, n_max + 1):
            bp = B_all[n-1, :] + pi1  # B_{R,n-1} + pi1
            A_all[n] = (A_all[n-1]
                        + bp @ mu_tilde
                        + 0.5 * bp @ self.Sigma @ bp
                        - delta0_R)
            B_all[n, :] = bp @ phi_tilde - self.delta1

        # Extract only the maturities in tips_curve
        mats = self.real_curve.columns.values.astype(int)
        A_r = A_all[mats]
        B_r = B_all[mats, :]

        return A_r, B_r

    def _estimate_pi(self):
        """
        Estimate inflation equation parameters pi0 (scalar) and pi1 (K-vector)
        by minimizing squared real yield fitting errors over the cross-section
        and time series of TIPS yields.

        Real yield: y_{R,t}^{(n)} = -1/n * (A_{R,n} + B_{R,n}' X_t)
        """
        tips_m = self.tips_curve_monthly.reindex(self.pc_factors_m.index)[
            self.selected_maturities_r
        ].dropna(how='all')
        X_m = self.pc_factors_m.reindex(tips_m.index).values  # T x K
        Y = tips_m.values                                       # T x N_R
        mats = np.array(self.selected_maturities_r, dtype=float)

        phi_tilde = self.phi_star
        mu_tilde = self.mu_star.flatten()

        def _real_yields_from_params(pi0_val, pi1_val):
            """Compute real model-implied yields for all maturities at all times."""
            n_max = int(mats.max())
            A_all = np.zeros(n_max + 1)
            B_all = np.zeros((n_max + 1, self.n_factors))
            delta0_R = self.delta0 - pi0_val

            for n in range(1, n_max + 1):
                bp = B_all[n-1, :] + pi1_val
                A_all[n] = (A_all[n-1]
                            + bp @ mu_tilde
                            + 0.5 * bp @ self.Sigma @ bp
                            - delta0_R)
                B_all[n, :] = bp @ phi_tilde - self.delta1

            # Extract maturities and compute annualized yields: -(A + B X') / (n/12)
            A_sel = A_all[mats.astype(int)]          # N_R,
            B_sel = B_all[mats.astype(int), :]       # N_R x K
            # yields: T x N_R  (annualized, matching the input TIPS yields)
            yields = -(A_sel[None, :] + (X_m @ B_sel.T)) / (mats[None, :] / 12)
            return yields

        def objective(params):
            pi0_val = params[0]
            pi1_val = params[1:]
            y_hat = _real_yields_from_params(pi0_val, pi1_val)
            resid = Y - y_hat
            return np.sum(resid ** 2)

        # Initial guess: pi0 ~ sample mean inflation / 12, pi1 ~ zeros
        pi0_init = self.inflation_monthly.mean()
        pi1_init = np.zeros(self.n_factors)
        x0 = np.concatenate([[pi0_init], pi1_init])

        result = minimize(objective, x0, method='L-BFGS-B',
                          options={'maxiter': 2000, 'ftol': 1e-12, 'gtol': 1e-8})

        pi0_hat = result.x[0]
        pi1_hat = result.x[1:]
        return pi0_hat, pi1_hat

    def _compute_yields(self, A, B, maturities):
        """
        Compute model-implied yields from affine coefficients using daily factors.
        y_t^{(n)} = -1/n * (A_n + B_n' X_t)

        Parameters
        ----------
        A : np.ndarray, shape (N,)
        B : np.ndarray, shape (N, K)
        maturities : array-like of int, column labels (monthly maturities)
        """
        mats = np.array(maturities, dtype=float)
        A = A.reshape(-1, 1)    # N x 1
        X_d = self.pc_factors_d.T.values  # K x T_d

        # yields: N x T_d  (annualized: divide by n_months/12)
        yields_raw = -(A + B @ X_d) / (mats[:, None] / 12)
        yields = pd.DataFrame(
            data=yields_raw.T,
            index=self.pc_factors_d.index,
            columns=maturities,
        )
        return yields

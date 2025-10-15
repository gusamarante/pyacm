import numpy as np
import pandas as pd

from numpy.linalg import inv
from sklearn.decomposition import PCA
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
            self.curve_monthly = curve.resample('M').mean()
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

    def fwd_curve(self, date=None):
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

            A[n] = A[n - 1] + B[n - 1, :] @ (self.mu - lambda0) + s0term + A[0]
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

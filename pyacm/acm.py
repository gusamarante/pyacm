import numpy as np
import pandas as pd

from numpy.linalg import inv
from sklearn.decomposition import PCA

from pyacm.utils import vec, vec_quad_form, commutation_matrix

# TODO Curve in daily frequency could be None
# TODO Make sure it works for DI Futures
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

    t: int
        Number of observations in the timeseries dimension

    n: int
        Number of observations in the cross-sectional dimension. Same
        as number of maturities available after returns are computed

    rx_m: pd.DataFrame
        Excess returns in monthly frquency

    rf_m: pandas.Series
        Risk-free rate in monthly frequency

    rf_d: pandas.Series
        Risk-free rate in daily frequency

    pc_factors_m: pandas.DataFrame
        Principal components in monthly frequency

    pc_loadings_m: pandas.DataFrame
        Factor loadings of the monthly PCs

    pc_explained_m: pandas.Series
        Percent of total variance explained by each monthly principal component

    pc_factors_d: pandas.DataFrame
        Principal components in daily frequency

    pc_loadings_d: pandas.DataFrame
        Factor loadings of the daily PCs

    pc_explained_d: pandas.Series
        Percent of total variance explained by each monthly principal component

    mu, phi, Sigma, v: numpy.array
        Estimates of the VAR(1) parameters, the first stage of estimation.
        The names are the same as the original paper

    a, beta, c, sigma2: numpy.array
        Estimates of the risk premium equation, the second stage of estimation.
        The names are the same as the original paper

    lambda0, lambda1: numpy.array
        Estimates of the price of risk parameters, the third stage of estimation.
        The names are the same as the original paper

    miy: pandas.DataFrame
        Model implied / fitted yields

    rny: pandas.DataFrame
        Risk neutral yields

    tp: pandas.DataFrame
        Term premium estimates

    er_loadings: pandas.DataFrame
        Loadings of the expected reutrns on the principal components

    er_hist_m: pandas.DataFrame
        Historical estimates of expected returns, computed in-sample, in monthly frequency

    er_hist_d: pandas.DataFrame
        Historical estimates of expected returns, computed in-sample, in daily frequency

    z_lambda: pandas.DataFrame
        Z-stat for inference on the price of risk parameters

    z_beta: pandas.DataFrame
        Z-stat for inference on the loadings of expected returns
    """

    def __init__(
            self,
            curve,
            curve_m=None,  # TODO Documentation
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
            and be equally spaced in monthly frequency. The labels of the
            columns do not matter, they be kept the same. Observations (index)
            must be of monthly frequency or higher. The index must be a
            pandas.DateTimeIndex.

        n_factors : int
            number of principal components to used as state variables.
        """

        # TODO assert columns of daily and monthly are the same
        # TODO assert monthly index frequency

        self.n_factors = n_factors
        self.curve = curve
        self.selected_maturities = selected_maturities

        if curve_m is None:
            self.curve_monthly = curve.resample('M').last()
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
        # TODO EVERYTHING RIGHT UP TO HERE

        # 2nd Step - Excess Returns
        self.beta, self.omega, self.beta_star = self._excess_return_regression()

        # 3rd Step - Convexity-adjusted price of risk
        self.lambda0, self.lambda1, self.mu_star, self.phi_star = self._retrieve_lambda()

        if self.curve.index.freqstr == 'M':
            X = self.pc_factors_m
            r1 = self.rf_m
        else:
            X = self.pc_factors_d
            r1 = self.rf_d

        self.miy = self._affine_recursions(self.lambda0, self.lambda1, X, r1)
        self.rny = self._affine_recursions(0, 0, X, r1)
        self.tp = self.miy - self.rny
        self.er_loadings, self.er_hist_m, self.er_hist_d = self._expected_return()
        self.z_lambda, self.z_beta = self._inference()

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
                fwd_miy.rename("Model Implied"),
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

    def _get_excess_returns(self):
        ttm = np.arange(1, self.n + 1) / 12
        log_prices = - (self.curve_monthly / 100) * ttm  # TODO this division by 100 has to go, test with decimal rates and check if output is the same
        rf = - log_prices.iloc[:, 0].shift(1)
        rx = (log_prices - log_prices.shift(1, axis=0).shift(-1, axis=1)).subtract(rf, axis=0)
        # rx = rx.shift(1, axis=1)  # TODO is this needed?

        rx = rx.dropna(how='all', axis=0).dropna(how='all', axis=1)
        # rf = rf.dropna()  # TODO Do I need to keep track of this?
        return rx

    def _get_pcs(self, curve_m, curve_d):

        curve_m_cut = curve_m.iloc[:, 2:]  # TODO The authors do this, do not know why
        curve_d_cut = curve_d.iloc[:, 2:]  # TODO The authors do this, do not know why

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

        # TODO Try a different normalization, keeping the PCs with their respective variances and loadings with unit norm.

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
        Z = np.vstack((np.ones((1, self.t)), X, self.v)).T  # Innovations and lagged X
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
        factors = np.hstack([np.ones((self.t, 1)), self.pc_factors_m.iloc[:-1].values])

        # Orthogonalize factors with respect to v
        v_proj = self.v.T @ np.linalg.pinv(self.v @ self.v.T) @ self.v
        factors = factors - v_proj @ factors

        adjustment = self.beta_star @ self.s0 + np.diag(self.omega).reshape(-1, 1)
        rx_adjusted = rx.values + (1 / 2) * np.tile(adjustment, (1, self.t)).T
        Y = (inv(factors.T @ factors) @ factors.T @ rx_adjusted).T

        # Compute Lambda
        X = self.beta
        Lambda = inv(X.T @ X) @ X.T @ Y
        lambda0 = Lambda[:, 0]
        lambda1 = Lambda[:, 1:]

        muStar = self.mu.reshape(-1) - lambda0
        phiStar = self.phi - lambda1

        return lambda0, lambda1, muStar, phiStar

    def _affine_recursions(self, lambda0, lambda1, X_in, r1):
        # TODO PAREI AQUI
        X = X_in.T.values[:, 1:]
        r1 = vec(r1.values)[-X.shape[1]:, :]

        A = np.zeros((1, self.n))
        B = np.zeros((self.n_factors, self.n))

        delta = r1.T @ np.linalg.pinv(np.vstack((np.ones((1, X.shape[1])), X)))
        delta0 = delta[[0], [0]]
        delta1 = delta[[0], 1:]

        A[0, 0] = - delta0
        B[:, 0] = - delta1

        for i in range(self.n - 1):
            A[0, i + 1] = A[0, i] + B[:, i].T @ (self.mu - lambda0) + 1 / 2 * (B[:, i].T @ self.Sigma @ B[:, i] + 0 * self.sigma2) - delta0
            B[:, i + 1] = B[:, i] @ (self.phi - lambda1) - delta1

        # Construct fitted yields
        ttm = np.arange(1, self.n + 1) / 12
        fitted_log_prices = (A.T + B.T @ X).T
        fitted_yields = - fitted_log_prices / ttm
        fitted_yields = pd.DataFrame(
            data=fitted_yields,
            index=self.curve.index[1:],
            columns=self.curve.columns,
        )
        return fitted_yields

    def _expected_return(self):
        """
        Compute the "expected return" and "convexity adjustment" terms, to get
        the expected return loadings and historical estimate

        Loadings are interpreted as the effect of 1sd of the PCs on the
        expected returns
        """
        stds = self.pc_factors_m.std().values[:, None].T
        er_loadings = (self.beta.T @ self.lambda1) * stds
        er_loadings = pd.DataFrame(
            data=er_loadings,
            columns=self.pc_factors_m.columns,
            index=self.selected_maturities,
        )

        # Monthly
        exp_ret = (self.beta.T @ (self.lambda1 @ self.pc_factors_m.T + self.lambda0)).values
        conv_adj = np.diag(self.beta.T @ self.Sigma @ self.beta) + self.sigma2
        er_hist = (exp_ret + conv_adj[:, None]).T
        er_hist_m = pd.DataFrame(
            data=er_hist,
            index=self.pc_factors_m.index,
            columns=self.curve.columns[:er_hist.shape[1]]
        )

        # Higher frequency
        exp_ret = (self.beta.T @ (self.lambda1 @ self.pc_factors_d.T + self.lambda0)).values
        conv_adj = np.diag(self.beta.T @ self.Sigma @ self.beta) + self.sigma2
        er_hist = (exp_ret + conv_adj[:, None]).T
        er_hist_d = pd.DataFrame(
            data=er_hist,
            index=self.pc_factors_d.index,
            columns=self.curve.columns[:er_hist.shape[1]]
        )

        return er_loadings, er_hist_m, er_hist_d

    def _inference(self):
        # TODO I AM NOT SURE THAT THIS SECTION IS CORRECT

        # Auxiliary matrices
        Z = self.pc_factors_m.copy().T
        Z = Z.values[:, 1:]
        Z = np.vstack((np.ones((1, self.t)), Z))

        Lamb = np.hstack((self.lambda0, self.lambda1))

        rho1 = np.zeros((self.n_factors + 1, 1))
        rho1[0, 0] = 1

        A_beta = np.zeros((self.n_factors * self.beta.shape[1], self.beta.shape[1]))

        for ii in range(self.beta.shape[1]):
            A_beta[ii * self.beta.shape[0]:(ii + 1) * self.beta.shape[0], ii] = self.beta[:, ii]

        BStar = np.squeeze(np.apply_along_axis(vec_quad_form, 1, self.beta.T))

        comm_kk = commutation_matrix(shape=(self.n_factors, self.n_factors))
        comm_kn = commutation_matrix(shape=(self.n_factors, self.beta.shape[1]))

        # Assymptotic variance of the betas
        v_beta = self.sigma2 * np.kron(np.eye(self.beta.shape[1]), inv(self.Sigma))

        # Assymptotic variance of the lambdas
        upsilon_zz = (1 / self.t) * Z @ Z.T
        v1 = np.kron(inv(upsilon_zz), self.Sigma)
        v2 = self.sigma2 * np.kron(inv(upsilon_zz), inv(self.beta @ self.beta.T))
        v3 = self.sigma2 * np.kron(Lamb.T @ self.Sigma @ Lamb, inv(self.beta @ self.beta.T))

        v4_sim = inv(self.beta @ self.beta.T) @ self.beta @ A_beta.T
        v4_mid = np.kron(np.eye(self.beta.shape[1]), self.Sigma)
        v4 = self.sigma2 * np.kron(rho1 @ rho1.T, v4_sim @ v4_mid @ v4_sim.T)

        v5_sim = inv(self.beta @ self.beta.T) @ self.beta @ BStar
        v5_mid = (np.eye(self.n_factors ** 2) + comm_kk) @ np.kron(self.Sigma, self.Sigma)
        v5 = 0.25 * np.kron(rho1 @ rho1.T, v5_sim @ v5_mid @ v5_sim.T)

        v6_sim = inv(self.beta @ self.beta.T) @ self.beta @ np.ones((self.beta.shape[1], 1))
        v6 = 0.5 * (self.sigma2 ** 2) * np.kron(rho1 @ rho1.T, v6_sim @ v6_sim.T)

        v_lambda_tau = v1 + v2 + v3 + v4 + v5 + v6

        c_lambda_tau_1 = np.kron(Lamb.T, inv(self.beta @ self.beta.T) @ self.beta)
        c_lambda_tau_2 = np.kron(rho1, inv(self.beta @ self.beta.T) @ self.beta @ A_beta.T @ np.kron(np.eye(self.beta.shape[1]), self.Sigma))
        c_lambda_tau = - c_lambda_tau_1 @ comm_kn @ v_beta @ c_lambda_tau_2.T

        v_lambda = v_lambda_tau + c_lambda_tau + c_lambda_tau.T

        # extract the z-tests
        sd_lambda = np.sqrt(np.diag(v_lambda).reshape(Lamb.shape, order='F'))
        sd_beta = np.sqrt(np.diag(v_beta).reshape(self.beta.shape, order='F'))

        z_beta = pd.DataFrame(self.beta / sd_beta, index=self.pc_factors_m.columns, columns=self.selected_maturities).T
        z_lambda = pd.DataFrame(Lamb / sd_lambda, index=self.pc_factors_m.columns, columns=[f"lambda {i}" for i in range(Lamb.shape[1])])

        return z_lambda, z_beta



import numpy as np
import pandas as pd


def vec(mat):
    """
    Stack the columns of `mat` into a column vector. If mat is a M x N matrix,
    then vec(mat) is an MN X 1 vector.

    Parameters
    ----------
        mat: numpy.array
    """
    vec_mat = mat.reshape((-1, 1), order='F')
    return vec_mat


def vec_quad_form(mat):
    """
    `vec` operation for quadratic forms

    Parameters
    ----------
        mat: numpy.array
    """
    return vec(np.outer(mat, mat))


def commutation_matrix(shape):
    """
    Generates the commutation matrix for a matrix with shape equal to `shape`.

    The definition of a commutation matrix `k` is:
        k @ vec(mat) = vec(mat.T)

    Parameters
    ----------
    shape : tuple
        2-d tuple (m, n) with the shape of `mat`
    """
    m, n = shape
    w = np.arange(m * n).reshape((m, n), order="F").T.ravel(order="F")
    k = np.eye(m * n)[w, :]
    return k


class FRED(object):
    """
    Wrapper for the data API of the FRED
    """

    def fetch(self, series_id):
        """
        Grabs series from the FRED website and returns them in a pandas
         dataframe

        Parameters
        ----------
        series_id: str, list, dict
            string with series ID, list of strings of the series ID or
            dict with series ID as keys and their desired names as values
        """

        if type(series_id) is list:

            df = pd.DataFrame()

            for cod in series_id:
                single_series = self._fetch_single_code(cod)
                df = pd.concat([df, single_series], axis=1)

            df.sort_index(inplace=True)

        elif type(series_id) is dict:

            df = pd.DataFrame()

            for cod in series_id.keys():
                single_series = self._fetch_single_code(cod)
                df = pd.concat([df, single_series], axis=1)

            df.columns = series_id.values()

        else:

            df = self._fetch_single_code(series_id)

        return df

    @staticmethod
    def _fetch_single_code(series_id):

        url = r'https://fred.stlouisfed.org/data/' + series_id + '.txt'
        df = pd.read_csv(url, sep='\t')
        series_start = df[df[df.columns[0]].str.contains('DATE\s+VALUE')].index[0] + 1
        df = df.loc[series_start:]
        df = df[df.columns[0]].str.split('\s+', expand=True)
        df = df[~(df[1] == '.')]
        df = pd.DataFrame(data=df[1].values.astype(float),
                          index=pd.to_datetime(df[0]),
                          columns=[series_id])
        df.index.rename('Date', inplace=True)

        return df

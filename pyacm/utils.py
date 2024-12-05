import numpy as np


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

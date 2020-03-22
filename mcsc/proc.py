import numpy as np

def prepare(a, B, C, s, T, Y): # see analyze(..) for parameter descriptions
    # add self-loops to nn graph
    a = a.copy()
    a.setdiag(1)
    colsums = np.array(a.sum(axis=0)).flatten()

    # very samples are sorted by batch (for null permutation)
    if any(np.diff(B) < 0):
        print('ERROR: samples must be sorted by batch')

    # translate sample-level outcome to cell-level outcome
    y = np.repeat(1000*Y, C).astype(np.float64)

    # add all-ones column to sample-level covariates
    if T is not None:
        T_ = np.hstack([T, np.ones((len(T), 1))])
    else:
        T_ = np.ones((len(Y), 1))

    # combine sample-level and cell-level covariates into one cell-level matrix
    # and create cell-level weight vector
    if s is not None:
        u = np.hstack([
            np.repeat(T_, C, axis=0),
            s]).astype(np.float64)
    else:
        u = np.repeat(T_, C, axis=0)
    w = np.repeat(Cs, Cs).astype(np.float64)

    # project covariates out of outcome and weight it
    y = y - u.dot(np.linalg.solve(u.T.dot(u / w[:,None]), u.T.dot(y / w)))
    y /= w

    return a, u, w, y

def conditional_permutation(B, Y, num): # assumes B is sorted and that Y and B line up
    starts = np.concatenate([
        [0],
        np.where(B[:-1] != B[1:])[0] + 1,
        [len(B)]])
    ix = np.concatenate([
        np.argsort(np.random.randn(j-i, num), axis=0) + i
        for i, j in zip(starts[:-1], starts[1:])
        ])
    return Y[ix]

def get_null(B, C, u, w, Y, num):
    nullY = conditional_permutation(Y.astype(np.float64), B, num=num)
    nully = np.repeat(1000*nullY, C, axis=0)
    nully -= u.dot(np.linalg.solve(u.T.dot(u / w[:,None]), u.T.dot(nully / w[:,None])))
    nully /= w[:,None]

    return nully

def get_null_mean(B, C, u, w, Y):
    nullMeans = np.array([
        np.mean(Y[B==b])
        for b in B
    ])
    nullmeans = np.repeat(1000*nullMeans, C, axis=0)
    nullmeans -= u.dot(np.linalg.solve(u.T.dot(u / w[:,None]), u.T.dot(nullmeans / w)))
    nullmeans /= w

    return nullmeans

import time, gc
import scipy.stats as st
def analyze(
    a, # adjacency matrix, cells x cells
    Y, # outcome, samples x 1 TODO: allow for cell-level outcome
    C=None, # sample sizes, samples x 1
    B=None, # batch ids, samples x 1
    T=None, # sample-level covariates, samples x num_sample_covariates
    s=None): # cell-level covariates, cells x num_cell_covariates
    
    def corr(g,h):
        return (g - g.mean()).dot(h - h.mean()) / (len(g)*g.std()*h.std())

    np.random.seed(0)
    Nnull = 500

    a, u, w, y = prepare(a, B, C, s, T, Y)
    nullmean = get_null_mean(B, C, u, w, Y)
    
    D, z, hits, bonf_z2, stds, mlp = dict(), dict(), dict(), dict(), dict(), dict()
    D[0] = y - nullmean
    Dnull = get_null(num=Nnull) - nullmean[:,None]

    i = 0
    t0 = time.time()
    while True:
        i += 1
        print(i, time.time() - t0, end=' ')
        D[i] = a.dot(D[i-1] / colsums)
        Dnull = a.dot(Dnull / colsums[:,None])
        stds[i] = np.sqrt((Dnull**2).mean(axis=1))
        print(corr(D[i-1], D[i]))

        z[i] = D[i] / stds[i]
        bonf_z2[i] = np.percentile(np.max((Dnull / stds[i][:,None])**2, axis=0), 95)
        print('Bonf:', (z[i]**2 > bonf_z2[i]).sum())

        mlp[i] = -(st.norm.logsf(np.abs(z[i])/np.log(10) + np.log10(2)))
        t, _, _ = sig.fdr(mlp[i], threshold=0.05, minuslog10p=True, st=False)
        hits[i] = mlp[i] >= (-np.log10(t) if t > 0 else np.inf)
        print('FDR:', hits[i].sum())

        #     if corr(Dold, D) > 0.99 or i > 100:
        if i >= 20:
            print()
            break

"""Shape-preserving interpolation (Fritsch-Carlson), used between load levels."""

import numpy as np


def pchip(x, y, xq):
    """
    Shape-preserving cubic interpolation (Fritsch-Carlson). `y` may have trailing axes.
    Monotonic data give a monotonic curve; queries outside the range are clamped to the ends.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    shape = y.shape[1:]
    y = y.reshape(len(x), -1)
    xq = np.clip(np.atleast_1d(np.asarray(xq, dtype=float)), x[0], x[-1])
    if len(x) == 1:
        return np.broadcast_to(y[0], (len(xq), y.shape[1])).reshape((len(xq),) + shape).copy()
    h = np.diff(x)
    delta = np.diff(y, axis=0) / h[:, None]
    d = np.zeros_like(y)
    if len(x) == 2:
        d[:] = delta[0]
    else:
        for k in range(1, len(x) - 1):
            same = delta[k - 1] * delta[k] > 0
            w1, w2 = 2 * h[k] + h[k - 1], h[k] + 2 * h[k - 1]
            with np.errstate(divide="ignore", invalid="ignore"):
                d[k] = np.where(same, (w1 + w2) / (w1 / delta[k - 1] + w2 / delta[k]), 0.0)
        for end, (h0, h1, d0, d1) in ((0, (h[0], h[1], delta[0], delta[1])),
                                      (-1, (h[-1], h[-2], delta[-1], delta[-2]))):
            slope = ((2 * h0 + h1) * d0 - h0 * d1) / (h0 + h1)
            slope = np.where(np.sign(slope) != np.sign(d0), 0.0, slope)
            slope = np.where((np.sign(d0) != np.sign(d1)) & (np.abs(slope) > 3 * np.abs(d0)), 3 * d0, slope)
            d[end] = slope
    i = np.clip(np.searchsorted(x, xq, side="right") - 1, 0, len(x) - 2)
    t = ((xq - x[i]) / h[i])[:, None]
    hi = h[i][:, None]
    out = ((2 * t ** 3 - 3 * t ** 2 + 1) * y[i] + (t ** 3 - 2 * t ** 2 + t) * hi * d[i]
           + (-2 * t ** 3 + 3 * t ** 2) * y[i + 1] + (t ** 3 - t ** 2) * hi * d[i + 1])
    return out.reshape((len(xq),) + shape)


# ----------------------------------------------------------------------------- field solutions

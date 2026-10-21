from __future__ import annotations
import math
import numpy as np

def permutation_entropy(signal, order=3, delay=1, normalize=True):
    x = np.asarray(signal, dtype=float)
    if order < 2 or delay < 1 or not np.isfinite(x).all(): return np.nan
    n = x.size - delay * (order - 1)
    if n < math.factorial(order) or n <= 0: return np.nan
    patterns = {}
    for i in range(n):
        window = x[i:i + delay*order:delay]
        if np.all(window == window[0]):
            ranks = tuple(range(order))
        else:
            # Stable sorting gives deterministic ordinal patterns for ties.
            ranks = tuple(np.argsort(window, kind="mergesort"))
        patterns[ranks] = patterns.get(ranks, 0) + 1
    p = np.array(list(patterns.values()), dtype=float) / n
    value = -np.sum(p * np.log(p))
    result = value / np.log(math.factorial(order)) if normalize else value
    return float(np.clip(result, 0.0, 1.0) if normalize else result)


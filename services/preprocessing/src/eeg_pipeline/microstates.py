from __future__ import annotations
import numpy as np

def microstate_metrics(epoch, sfreq, n_states=4, random_state=42, max_samples=20000):
    """Simple modified k-means on normalized topographies; labels are local, never A-D."""
    x = epoch - epoch.mean(axis=0, keepdims=True); norms=np.linalg.norm(x, axis=0); valid=norms>0
    maps=(x[:, valid]/norms[valid]).T
    if len(maps) > max_samples:
        rng=np.random.default_rng(random_state)
        maps=maps[rng.choice(len(maps), max_samples, replace=False)]
    if len(maps) < n_states: return []
    rng=np.random.default_rng(random_state); centers=maps[rng.choice(len(maps), n_states, replace=False)]
    for _ in range(50):
        labels=np.argmax(np.abs(maps @ centers.T), axis=1); new=[]
        for k in range(n_states):
            members=maps[labels==k]
            new.append(members.mean(axis=0) if len(members) else centers[k])
        new=np.asarray(new); new/=np.maximum(np.linalg.norm(new, axis=1, keepdims=True), 1e-12)
        if np.allclose(new, centers): break
        centers=new
    labels=np.argmax(np.abs(maps @ centers.T), axis=1)
    results=[]
    for k in range(n_states):
        idx=np.flatnonzero(labels==k); coverage=float(np.mean(labels==k))
        runs=idx[np.r_[True, np.diff(idx)>1]] if len(idx) else np.array([], dtype=int)
        duration=float(np.mean([len(r) for r in np.split(idx, np.flatnonzero(np.diff(idx)>1)+1)]))/sfreq*1000 if len(idx) else np.nan
        results.append({"microstate_class": k, "duration_ms": duration, "occurrence_per_s": len(runs)/(len(labels)/sfreq), "coverage": coverage})
    return results


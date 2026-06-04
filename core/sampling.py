"""Latin Hypercube Sampling for initial parameter space exploration."""

import numpy as np

# 反算參數：2 個 Young's modulus 縮放係數
PARAM_NAMES = ["k_E", "k_E_fault"]

PARAM_BOUNDS = {
    "k_E":       (0.3, 3.0),   # Young 整體縮放係數
    "k_E_fault": (0.1, 1.0),   # 斷層帶額外縮放
}


def latin_hypercube_sample(n_samples, seed=42):
    """Generate n_samples parameter sets using Latin Hypercube Sampling.

    Returns a list of dicts, each with keys matching PARAM_NAMES.
    """
    rng = np.random.default_rng(seed)
    n_params = len(PARAM_NAMES)

    samples = np.zeros((n_samples, n_params))
    for j in range(n_params):
        perm = rng.permutation(n_samples)
        u = (perm + rng.random(n_samples)) / n_samples
        lo, hi = PARAM_BOUNDS[PARAM_NAMES[j]]
        samples[:, j] = lo + u * (hi - lo)

    result = []
    for i in range(n_samples):
        result.append({name: float(samples[i, k])
                       for k, name in enumerate(PARAM_NAMES)})
    return result


def normalize(params_dict):
    """Map physical params to [0, 1]^N."""
    return np.array([
        (params_dict[name] - PARAM_BOUNDS[name][0]) /
        (PARAM_BOUNDS[name][1] - PARAM_BOUNDS[name][0])
        for name in PARAM_NAMES
    ])


def denormalize(x):
    """Map [0,1]^N array back to physical units. Returns a dict."""
    result = {}
    for k, name in enumerate(PARAM_NAMES):
        lo, hi = PARAM_BOUNDS[name]
        result[name] = float(np.clip(x[k], 0.0, 1.0) * (hi - lo) + lo)
    return result


def params_to_array(params_dict):
    """Convert params dict to numpy array in PARAM_NAMES order."""
    return np.array([params_dict[n] for n in PARAM_NAMES])


def clip_to_bounds(params_dict):
    """Clip parameter values to their physical bounds."""
    return {
        name: float(np.clip(params_dict[name],
                            PARAM_BOUNDS[name][0],
                            PARAM_BOUNDS[name][1]))
        for name in PARAM_NAMES
    }

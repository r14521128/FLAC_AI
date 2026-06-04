"""Calibration Agent: Gaussian Process Surrogate + Expected Improvement."""

import numpy as np
from scipy.stats import norm
from scipy.optimize import minimize
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, WhiteKernel, ConstantKernel

from core.sampling import PARAM_NAMES, PARAM_BOUNDS, normalize, denormalize, params_to_array

N_PARAMS = len(PARAM_NAMES)


# ---------------------------------------------------------------------------
# Kernel: Matern(5/2) with automatic length-scale + noise
# ---------------------------------------------------------------------------
def _build_kernel():
    return (
        ConstantKernel(1.0, (1e-3, 1e3))
        * Matern(length_scale=np.ones(N_PARAMS), length_scale_bounds=(1e-3, 100.0), nu=2.5)
        + WhiteKernel(noise_level=1e-6, noise_level_bounds=(1e-10, 1e-1))
    )


class CalibrationAgent:
    """Manages the Gaussian Process surrogate and suggests next candidates."""

    def __init__(self, n_restarts=5, exploration_weight=0.01):
        self.n_restarts = n_restarts
        self.xi = exploration_weight
        self.gp = GaussianProcessRegressor(
            kernel=_build_kernel(),
            n_restarts_optimizer=5,
            normalize_y=True,
            alpha=1e-6,
        )
        self._X_norm = None
        self._y = None

    # ------------------------------------------------------------------
    def fit(self, runs):
        """Train the GP on completed simulation runs."""
        if len(runs) < 2:
            return False

        X = np.array([normalize({n: r[n] for n in PARAM_NAMES}) for r in runs])
        y = np.array([r["loss"] for r in runs])

        self._X_norm = X
        self._y = y
        self.gp.fit(X, y)
        print("[CalibAgent] GP trained on {:d} points. "
              "Best loss so far: {:.6f}".format(len(runs), float(y.min())))
        return True

    # ------------------------------------------------------------------
    def _expected_improvement(self, x_norm):
        x = x_norm.reshape(1, -1)
        mu, sigma = self.gp.predict(x, return_std=True)
        mu = mu[0]
        sigma = sigma[0]
        if sigma < 1e-10:
            return 0.0
        f_best = self._y.min()
        z = (f_best - mu - self.xi) / sigma
        ei = (f_best - mu - self.xi) * norm.cdf(z) + sigma * norm.pdf(z)
        return float(max(ei, 0.0))

    def _neg_ei(self, x_norm):
        return -self._expected_improvement(x_norm)

    # ------------------------------------------------------------------
    def suggest(self):
        """Return the parameter dict that maximises Expected Improvement."""
        if self._X_norm is None:
            raise RuntimeError("Call fit() before suggest().")

        best_ei = -np.inf
        best_x = None
        rng = np.random.default_rng()

        for _ in range(self.n_restarts):
            x0 = rng.random(N_PARAMS)
            res = minimize(
                self._neg_ei,
                x0,
                bounds=[(0.0, 1.0)] * N_PARAMS,
                method="L-BFGS-B",
                options={"maxiter": 200},
            )
            ei = -res.fun
            if ei > best_ei:
                best_ei = ei
                best_x = res.x

        params = denormalize(best_x)
        print("[CalibAgent] Suggested params (EI={:.6f}): {}".format(
            best_ei,
            {k: round(v, 5) for k, v in params.items()}
        ))
        return params

    # ------------------------------------------------------------------
    def predict(self, params_dict):
        """Predict (mean, std) loss for a parameter dict."""
        x = normalize(params_dict).reshape(1, -1)
        mu, sigma = self.gp.predict(x, return_std=True)
        return float(mu[0]), float(sigma[0])

    # ------------------------------------------------------------------
    def is_ready(self, min_points=5):
        """True when GP has enough data to make reliable suggestions."""
        return self._y is not None and len(self._y) >= min_points

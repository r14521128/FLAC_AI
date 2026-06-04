# -*- coding: utf-8 -*-
"""Parameter injection script for FLAC3D 6.0 (Python 2.7 embedded).

This script is called from within FLAC3D via:
    python run_simulation.py

It reads flac3d/params.json written by the external orchestrator and
applies Young's modulus scaling to the 5 rock-type groups.

Calibrated parameters:
    k_E       : overall Young's modulus scaling coefficient (0.3 ~ 3.0)
    k_E_fault : additional scaling for Fault zone (0.1 ~ 1.0)

All other properties (cohesion, friction, tension, dilation, density,
Poisson's ratio) are fixed from lab test medians.
"""

from __future__ import print_function
import json
import os
import sys
import itasca as it

# ---------------------------------------------------------------------------
# Paths (relative to FLAC3D working directory = project root)
# ---------------------------------------------------------------------------
PARAMS_FILE = os.path.join("flac3d", "params.json")

# ---------------------------------------------------------------------------
# Rock group names as defined in the model
# ---------------------------------------------------------------------------
GROUPS = ["SS_NK", "Interbedded_ST", "SH_ST", "SS_NC", "Fault"]

# ---------------------------------------------------------------------------
# Base Young's modulus per group (Pa)
# ---------------------------------------------------------------------------
BASE_YOUNG = {
    "SS_NK":          2.0e9,
    "Interbedded_ST": 1.0e9,
    "SH_ST":          1.5e9,
    "SS_NC":          2.5e9,
    "Fault":          0.5e9,
}

# ---------------------------------------------------------------------------
# Fixed material properties from lab tests
# ---------------------------------------------------------------------------
FIXED_PROPS = {
    "SS_NK": {
        "density": 2650.0,
        "poisson": 0.25,
        "cohesion": 0.08e6,
        "friction": 35.0,
        "tension": 0.008e6,
        "dilation": 3.0,
    },
    "Interbedded_ST": {
        "density": 2550.0,
        "poisson": 0.28,
        "cohesion": 0.06e6,
        "friction": 30.0,
        "tension": 0.006e6,
        "dilation": 3.0,
    },
    "SH_ST": {
        "density": 2600.0,
        "poisson": 0.27,
        "cohesion": 0.07e6,
        "friction": 32.0,
        "tension": 0.007e6,
        "dilation": 3.0,
    },
    "SS_NC": {
        "density": 2700.0,
        "poisson": 0.23,
        "cohesion": 0.10e6,
        "friction": 38.0,
        "tension": 0.010e6,
        "dilation": 3.0,
    },
    "Fault": {
        "density": 2400.0,
        "poisson": 0.32,
        "cohesion": 0.02e6,
        "friction": 25.0,
        "tension": 0.002e6,
        "dilation": 3.0,
    },
}


def load_params():
    if not os.path.isfile(PARAMS_FILE):
        raise IOError("params.json not found: " + PARAMS_FILE)
    with open(PARAMS_FILE, "r") as f:
        p = json.load(f)
    required = {"k_E", "k_E_fault"}
    missing = required - set(p.keys())
    if missing:
        raise ValueError("Missing keys in params.json: " + str(missing))
    return p


def apply_params(params):
    """Inject Young's modulus and fixed properties into all zone groups."""
    k_E = float(params["k_E"])
    k_E_fault = float(params["k_E_fault"])

    for grp in GROUPS:
        # Compute Young's modulus
        if grp == "Fault":
            young = k_E * k_E_fault * BASE_YOUNG[grp]
        else:
            young = k_E * BASE_YOUNG[grp]

        # Bulk and shear modulus from Young + Poisson
        poisson = FIXED_PROPS[grp]["poisson"]
        bulk = young / (3.0 * (1.0 - 2.0 * poisson))
        shear = young / (2.0 * (1.0 + poisson))

        # Fixed strength properties
        props = FIXED_PROPS[grp]

        # Assign elastic properties
        cmd_elastic = (
            "zone property bulk {bulk:.2f} shear {shear:.2f} "
            "density {dens:.2f} "
            "range group '{grp}'"
        ).format(bulk=bulk, shear=shear, dens=props["density"], grp=grp)

        # Assign strength properties (Mohr-Coulomb)
        cmd_strength = (
            "zone property cohesion {coh:.2f} "
            "friction {fric:.4f} "
            "tension {ten:.2f} "
            "dilation {dil:.4f} "
            "range group '{grp}'"
        ).format(
            coh=props["cohesion"],
            fric=props["friction"],
            ten=props["tension"],
            dil=props["dilation"],
            grp=grp,
        )

        print("[run_simulation] " + cmd_elastic)
        it.command(cmd_elastic)
        print("[run_simulation] " + cmd_strength)
        it.command(cmd_strength)

    print("[run_simulation] Parameters applied successfully.")
    print("[run_simulation] k_E={:.4f}, k_E_fault={:.4f}".format(k_E, k_E_fault))
    for grp in GROUPS:
        if grp == "Fault":
            young = k_E * k_E_fault * BASE_YOUNG[grp]
        else:
            young = k_E * BASE_YOUNG[grp]
        print("  {}: Young={:.3e} Pa".format(grp, young))


def main():
    params = load_params()
    print("[run_simulation] Loaded params: " + str(params))
    apply_params(params)


if __name__ == "__main__":
    main()

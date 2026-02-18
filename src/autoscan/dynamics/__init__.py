"""
AutoScan Molecular Dynamics Module

Module 8: Post-mutation structure relaxation and energy minimization.

This module uses OpenMM to relax protein structures after in-silico mutagenesis,
resolving steric clashes and vacuum holes created by residue substitutions.

Key Components:
- EnergyMinimizer: Main class for structure relaxation
- relax_structure(): Convenience function wrapper
- Force Field: AMBER14 + OBC2 implicit solvent
- Integrator: Langevin thermostat at 300K

Usage:
    from autoscan.dynamics.minimizer import EnergyMinimizer
    minimizer = EnergyMinimizer()
    relaxed_pdb = minimizer.minimize(Path("mutant.pdb"))

Installation:
    Requires OpenMM (install via conda):
    conda install -c conda-forge openmm pdbfixer

Author: AutoScan Development Team
Date: February 2026
"""

from autoscan.dynamics.minimizer import (
    EnergyMinimizer,
    relax_structure,
    is_openmm_available,
    HAS_OPENMM
)

__all__ = [
    'EnergyMinimizer',
    'relax_structure',
    'is_openmm_available',
    'HAS_OPENMM'
]

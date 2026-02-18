"""
Molecular Dynamics Module: Structure Relaxation & Energy Minimization

This module provides post-mutation structure relaxation using OpenMM.
It resolves steric clashes and "holes" created by in-silico mutagenesis
(e.g., D87G causing vacuum pocket defects in Gyrase inhibitor binding).

The EnergyMinimizer uses implicit solvent (OBC2) for efficiency while
maintaining accuracy, avoiding the computational cost of explicit water boxes.

Technical:
- Force Field: AMBER14 (amber14-all.xml)
- Solvent: Implicit OBC2 (generalized Born model)
- Integrator: Langevin (300K, 1ps friction, 0.004ps timestep)
- Constraints: Hydrogen bonds (HBonds)
- Stopping Criterion: 10 kcal/mol/Å (typical for MD pre-equilibration)

Usage:
    minimizer = EnergyMinimizer()
    relaxed_pdb = minimizer.minimize(
        pdb_path=Path("structure_mutant.pdb"),
        output_path=Path("structure_mutant_relaxed.pdb")
    )

Dependencies:
    - openmm (>=8.0) - Install via: conda install -c conda-forge openmm pdbfixer
    - pathlib (builtin)
    - autoscan.utils.logger

Author: AutoScan Development Team (Module 8)
Date: February 2026
"""

from pathlib import Path
from typing import Optional
import sys

# Handle OpenMM import gracefully
try:
    from openmm import app
    import openmm as mm
    from openmm import unit
    HAS_OPENMM = True
except ImportError:
    HAS_OPENMM = False

from autoscan.utils import get_logger

logger = get_logger(__name__)


class EnergyMinimizer:
    """
    Molecular dynamics energy minimizer using OpenMM.
    
    Relaxes protein structures post-mutation to resolve steric clashes
    and atomic overlap (vacuum holes). Uses implicit solvent for speed.
    """

    def __init__(self):
        """
        Initialize the Force Field and simulation environment.
        
        Uses:
        - Force Field: AMBER14 (amber14-all.xml) for proteins
        - Solvent: Implicit OBC2 (Generalized Born with molecular volume correction)
        
        These are standard choices for protein MD simulations,
        providing good accuracy-to-speed tradeoff.
        """
        if not HAS_OPENMM:
            logger.warning(
                "OpenMM not found. Energy minimization will be skipped. "
                "Install via: conda install -c conda-forge openmm pdbfixer"
            )
            return

        try:
            # Load AMBER14 force field and implicit solvent model
            self.forcefield = app.ForceField(
                'amber14-all.xml',      # Protein force field
                'implicit/obc2.xml'     # Implicit solvent (OBC2 Generalized Born)
            )
            logger.info("Force field loaded: AMBER14 + OBC2 implicit solvent")
        except Exception as e:
            logger.error(f"Failed to load force field: {e}")
            self.forcefield = None

    def minimize(
        self,
        pdb_path: Path,
        output_path: Optional[Path] = None,
        max_iterations: int = 1000,
        tolerance: float = 10.0,  # kcal/mol/Å
        remove_h_bonds: bool = False
    ) -> Path:
        """
        Energy minimize a protein structure using OpenMM.
        
        Procedure:
        1. Load PDB structure
        2. Create OpenMM System (NoCutoff, HBond constraints)
        3. Create Langevin integrator (300K, thermostat)
        4. Run energy minimization to convergence
        5. Save minimized coordinates to output PDB
        
        Args:
            pdb_path: Path to input PDB file (mutated structure).
            output_path: Path for output PDB. Auto-generated if None.
            max_iterations: Maximum minimization steps (default: 1000).
            tolerance: Convergence criterion in kcal/mol/Å (default: 10.0).
            remove_h_bonds: If True, remove non-constrained H-bonds.
        
        Returns:
            Path to relaxed PDB file. Returns original path if minimization fails.
        
        Example:
            >>> minimizer = EnergyMinimizer()
            >>> relaxed = minimizer.minimize(
            ...     Path("gyrase_d87g.pdb"),
            ...     output_path=Path("gyrase_d87g_relaxed.pdb")
            ... )
        """
        
        # Fail-safe: if OpenMM not available, return original path
        if not HAS_OPENMM:
            logger.warning(
                f"OpenMM not available. Returning original structure: {pdb_path}"
            )
            return Path(pdb_path)

        if self.forcefield is None:
            logger.warning(
                f"Force field not initialized. Returning original structure: {pdb_path}"
            )
            return Path(pdb_path)

        pdb_path = Path(pdb_path)
        if not pdb_path.exists():
            logger.error(f"PDB file not found: {pdb_path}")
            return pdb_path

        if output_path is None:
            output_path = pdb_path.parent / f"{pdb_path.stem}_relaxed.pdb"
        else:
            output_path = Path(output_path)

        try:
            logger.info(f"Starting energy minimization: {pdb_path.name}")
            logger.info(f"  Force Field: AMBER14 + OBC2")
            logger.info(f"  Max Iterations: {max_iterations}")
            logger.info(f"  Convergence: {tolerance} kcal/mol/Å")

            # ================================================================
            # STEP 1: Load PDB structure
            # ================================================================
            # Note: Convert PDBQT to PDB if needed
            pdb_path = Path(pdb_path)
            if pdb_path.suffix.lower() == '.pdbqt':
                # PDBQT files have extra fields, use PDB version if available
                pdb_alternative = pdb_path.with_suffix('.pdb')
                if pdb_alternative.exists():
                    pdb_path = pdb_alternative
                    logger.info(f"Using PDB file instead of PDBQT: {pdb_path}")
                else:
                    logger.warning(f"PDBQT file provided but PDB not found. Returning original structure.")
                    return Path(pdb_path)
            
            pdb = app.PDBFile(str(pdb_path))
            logger.info(f"  Loaded PDB: {len(pdb.topology.atoms)} atoms")

            # ================================================================
            # STEP 2: Create OpenMM System
            # ================================================================
            # NoCutoff: No cut-off for non-bonded interactions (implicit solvent)
            # constraints: HBonds - constrain hydrogen bond lengths (faster, stable)
            system = self.forcefield.createSystem(
                pdb.topology,
                nonbondedMethod=app.NoCutoff,
                constraints=app.HBonds,
                removeCMMotion=True
            )
            logger.info(f"  Created system with {system.getNumParticles()} particles")

            # ================================================================
            # STEP 3: Create Langevin Integrator
            # ================================================================
            # 300K (physiological temperature)
            # 1.0/unit.picoseconds (friction coefficient, ~1ps relaxation time)
            # 0.004*unit.picoseconds (timestep, 4fs - stable for constrained H-bonds)
            integrator = mm.LangevinMiddleIntegrator(
                300 * unit.kelvin,              # Temperature
                1.0 / unit.picosecond,          # Friction coefficient
                0.004 * unit.picosecond         # Timestep (4 fs)
            )
            logger.info("  Created Langevin integrator (300K, 1ps friction, 4fs step)")

            # ================================================================
            # STEP 4: Create Simulation
            # ================================================================
            simulation = app.Simulation(
                pdb.topology,
                system,
                integrator
            )
            simulation.context.setPositions(pdb.positions)
            logger.info("  Simulation context created")

            # ================================================================
            # CRITICAL STEP: Energy Minimization
            # ================================================================
            logger.info("  Running energy minimization...")
            initial_energy = simulation.context.getState(getEnergy=True).getPotentialEnergy()
            logger.info(f"  Initial potential energy: {initial_energy.in_units_of(unit.kilocalories_per_mole):.2f} kcal/mol")

            # The magic fix: minimize energy to relax the structure
            # This resolves the "hole" left by mutation (e.g., D87G)
            simulation.minimizeEnergy(
                maxIterations=max_iterations,
                tolerance=tolerance * unit.kilocalories_per_mole / unit.angstrom
            )

            final_energy = simulation.context.getState(getEnergy=True).getPotentialEnergy()
            energy_change = (initial_energy - final_energy).in_units_of(unit.kilocalories_per_mole)
            logger.info(f"  Final potential energy: {final_energy.in_units_of(unit.kilocalories_per_mole):.2f} kcal/mol")
            logger.info(f"  Energy change: {energy_change:.2f} kcal/mol")

            if energy_change < 0.5:
                logger.warning(
                    f"  Small energy change ({energy_change:.2f} kcal/mol). "
                    "Structure may already be well-optimized."
                )
            else:
                logger.info(f"  ✓ Structure successfully relaxed ({energy_change:.2f} kcal/mol reduction)")

            # ================================================================
            # STEP 5: Save Minimized Structure
            # ================================================================
            state = simulation.context.getState(getPositions=True)
            minimized_positions = state.getPositions()

            # Write relaxed structure to output PDB
            with open(output_path, 'w') as f:
                app.PDBFile.writeFile(
                    pdb.topology,
                    minimized_positions,
                    f
                )

            logger.info(f"  ✓ Relaxed structure saved: {output_path}")
            logger.info("Energy minimization complete!")
            
            return output_path

        except Exception as e:
            logger.error(f"Energy minimization failed: {str(e)}")
            logger.warning(f"Returning original structure (fail-safe): {pdb_path}")
            return pdb_path

    def minimize_trajectory(
        self,
        pdb_path: Path,
        num_steps: int = 1000,
        output_prefix: Optional[str] = None,
        save_interval: int = 100
    ) -> Path:
        """
        Run MD simulation and save trajectory (advanced).
        
        This is a more advanced method that saves intermediate frames,
        useful for visualizing the relaxation process.
        
        Args:
            pdb_path: Path to input PDB file.
            num_steps: Number of MD steps to run.
            output_prefix: Prefix for trajectory files.
            save_interval: Save frame every N steps.
        
        Returns:
            Path to final minimized PDB.
        
        Note:
            This is experimental and requires additional setup for
            trajectory file formats (PDB, DCD, etc.).
        """
        logger.info("Trajectory-based MD (experimental) - not yet implemented")
        # Future enhancement: support trajectory output
        return self.minimize(pdb_path)


# ============================================================================
# Convenience Functions
# ============================================================================

def relax_structure(
    pdb_path: Path,
    output_path: Optional[Path] = None
) -> Path:
    """
    Convenience function: Relax a protein structure.
    
    Args:
        pdb_path: Path to input PDB (mutated protein).
        output_path: Path for output (auto-generated if None).
    
    Returns:
        Path to relaxed PDB.
    
    Usage:
        >>> from autoscan.dynamics.minimizer import relax_structure
        >>> relaxed = relax_structure(Path("gyrase_d87g.pdb"))
    """
    minimizer = EnergyMinimizer()
    return minimizer.minimize(pdb_path, output_path)


def is_openmm_available() -> bool:
    """Check if OpenMM is installed and functional."""
    return HAS_OPENMM


if __name__ == "__main__":
    # Demo/testing
    print("\n" + "="*80)
    print("AutoScan Molecular Dynamics Module (Module 8)")
    print("="*80)
    
    if not HAS_OPENMM:
        print("\n⚠ OpenMM is not installed.")
        print("Install via: conda install -c conda-forge openmm pdbfixer")
        print("\nFeatures will degrade gracefully (minimizer will return original PDB)")
        sys.exit(0)
    
    print("\n✓ OpenMM is available")
    print(f"✓ OpenMM Version: {mm.__version__}")
    print("\nTo use the minimizer:")
    print("  from autoscan.dynamics.minimizer import EnergyMinimizer")
    print("  minimizer = EnergyMinimizer()")
    print("  relaxed = minimizer.minimize(Path('structure_mutant.pdb'))")

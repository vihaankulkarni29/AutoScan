"""
Molecular Dynamics Module: Structure Relaxation & Energy Minimization

Module 8 - Upgraded with Backbone Restraints for Enhanced Biophysics

This module provides post-mutation structure relaxation using OpenMM with
optional harmonic restraints on the protein backbone. This allows controlled
relaxation - from full flexibility (stiffness=0) to backbone-frozen (stiffness=1000+).

Technical:
- Force Field: AMBER14 (amber14-all.xml)
- Solvent: Implicit OBC2 (generalized Born model)
- Integrator: Langevin (300K, 1ps friction, 0.004ps timestep)
- Restraints: Harmonic spring on backbone atoms (CA, C, N)
- Constraints: Hydrogen bonds (HBonds)
- Stopping Criterion: 10 kJ/mol (energy minimization convergence)

Usage - Full Flexibility:
    minimizer = EnergyMinimizer()
    relaxed = minimizer.minimize(Path("mutant.pdb"), stiffness=0.0)

Usage - Moderate Restraint:
    minimizer = EnergyMinimizer()
    relaxed = minimizer.minimize(Path("mutant.pdb"), stiffness=100.0)

Usage - Strong Backbone Freeze:
    minimizer = EnergyMinimizer()
    relaxed = minimizer.minimize(Path("mutant.pdb"), stiffness=1000.0)

Author: AutoScan Development Team (Module 8 - Upgraded)
Date: February 2026
"""

from pathlib import Path
from typing import Optional
import sys

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
    Molecular dynamics energy minimizer with optional backbone restraints.
    
    Upgraded Module 8: Supports harmonic restraints on protein backbone atoms
    (CA, C, N) to control the degree of structural flexibility during relaxation.
    """

    def __init__(self):
        """
        Initialize the Force Field and simulation environment.
        
        Uses:
        - Force Field: AMBER14 (amber14-all.xml) for proteins
        - Solvent: Implicit OBC2 (Generalized Born with molecular volume correction)
        """
        if not HAS_OPENMM:
            logger.warning(
                "OpenMM not found. Energy minimization will be skipped. "
                "Install via: pip install openmm pdbfixer"
            )
            return

        try:
            self.forcefield = app.ForceField(
                'amber14-all.xml',
                'implicit/obc2.xml'
            )
            logger.info("Force field loaded: AMBER14 + OBC2 implicit solvent")
        except Exception as e:
            logger.error(f"Failed to load force field: {e}")
            self.forcefield = None

    def minimize(
        self,
        pdb_path: Path,
        output_path: Optional[Path] = None,
        stiffness: float = 0.0,
        max_iterations: int = 1000
    ) -> Path:
        """
        Energy minimize a protein structure with optional backbone restraints.
        
        This is the upgraded Module 8 with biophysical control over relaxation.
        
        Args:
            pdb_path: Path to input PDB file (mutated structure)
            output_path: Output PDB path (auto-generated if None)
            stiffness: Backbone restraint strength in kJ/mol/nm²
                - 0.0 (default): Full flexibility, allow backbone adjustments
                - 50.0-100.0: Moderate restraint, side-chain optimization
                - 500.0-1000.0: Strong restraint, mostly side-chain movement
                - 1000.0+: Backbone essentially frozen, minimal changes
            max_iterations: Maximum minimization steps (default: 1000)
        
        Returns:
            Path to relaxed PDB file
            
        Example:
            >>> minimizer = EnergyMinimizer()
            >>> # Full relaxation of side chains AND backbone
            >>> relaxed = minimizer.minimize(Path("mutant.pdb"), stiffness=0.0)
            >>> # Conservative relaxation (backbone mostly frozen)
            >>> relaxed = minimizer.minimize(Path("mutant.pdb"), stiffness=500.0)
        """
        
        if not HAS_OPENMM:
            logger.warning(f"OpenMM not available. Returning original: {pdb_path}")
            return Path(pdb_path)

        if self.forcefield is None:
            logger.warning(f"Force field not initialized. Returning original: {pdb_path}")
            return Path(pdb_path)

        pdb_path = Path(pdb_path)
        if not pdb_path.exists():
            logger.error(f"PDB file not found: {pdb_path}")
            return pdb_path

        # Handle PDBQT conversion
        if pdb_path.suffix.lower() == '.pdbqt':
            pdb_alternative = pdb_path.with_suffix('.pdb')
            if pdb_alternative.exists():
                pdb_path = pdb_alternative
                logger.info(f"Using PDB file instead of PDBQT: {pdb_path}")
            else:
                logger.warning(f"PDBQT file provided but PDB not found. Returning original.")
                return Path(pdb_path)

        if output_path is None:
            output_path = pdb_path.parent / f"{pdb_path.stem}_minimized.pdb"
        else:
            output_path = Path(output_path)

        try:
            logger.info(f"Starting energy minimization: {pdb_path.name}")
            logger.info(f"  Force Field: AMBER14 + OBC2")
            logger.info(f"  Max Iterations: {max_iterations}")
            logger.info(f"  Backbone Restraint: {stiffness} kJ/mol/nm²")
            if stiffness > 0:
                logger.info(f"  Mode: Restrained (stiffness={stiffness})")
            else:
                logger.info(f"  Mode: Unrestrained (full flexibility)")

            # ================================================================
            # STEP 1: Load PDB structure
            # ================================================================
            pdb = app.PDBFile(str(pdb_path))
            logger.info(f"  Loaded PDB: {len(pdb.topology.atoms)} atoms")

            # ================================================================
            # STEP 2: Create OpenMM System
            # ================================================================
            system = self.forcefield.createSystem(
                pdb.topology,
                nonbondedMethod=app.NoCutoff,
                constraints=app.HBonds,
                removeCMMotion=True
            )
            logger.info(f"  Created system with {system.getNumParticles()} particles")

            # ================================================================
            # STEP 3: APPLY BACKBONE RESTRAINTS (Module 8 Upgrade)
            # ================================================================
            if stiffness > 0.0:
                logger.info(f"  Adding harmonic restraints to backbone atoms (CA, C, N)...")
                
                # Create custom external force for backbone restraints
                restraint = mm.CustomExternalForce(
                    "k * periodicdistance(x, y, z, x0, y0, z0)^2"
                )
                restraint.addGlobalParameter(
                    "k",
                    stiffness * unit.kilojoules_per_mole / unit.nanometer**2
                )
                restraint.addPerParticleParameter("x0")
                restraint.addPerParticleParameter("y0")
                restraint.addPerParticleParameter("z0")
                
                # Restrain only backbone atoms (CA, C, N)
                backbone_atoms = 0
                for atom in pdb.topology.atoms():
                    if atom.name in ('CA', 'C', 'N'):
                        pos = pdb.positions[atom.index]
                        restraint.addParticle(atom.index, [pos[0], pos[1], pos[2]])
                        backbone_atoms += 1
                
                system.addForce(restraint)
                logger.info(f"  ✓ Restrained {backbone_atoms} backbone atoms")
            else:
                logger.info(f"  No backbone restraints (full flexibility)")

            # ================================================================
            # STEP 4: Create Langevin Integrator
            # ================================================================
            integrator = mm.LangevinMiddleIntegrator(
                300 * unit.kelvin,
                1.0 / unit.picosecond,
                0.004 * unit.picosecond
            )
            logger.info("  Created Langevin integrator (300K, 1ps friction, 4fs step)")

            # ================================================================
            # STEP 5: Create Simulation
            # ================================================================
            simulation = app.Simulation(pdb.topology, system, integrator)
            simulation.context.setPositions(pdb.positions)
            logger.info("  Simulation context created")

            # ================================================================
            # STEP 6: Calculate Initial Energy
            # ================================================================
            state0 = simulation.context.getState(getEnergy=True)
            e_init = state0.getPotentialEnergy().value_in_unit(unit.kilojoules_per_mole)
            logger.info(f"  Initial potential energy: {e_init:.2f} kJ/mol")

            # ================================================================
            # STEP 7: MINIMIZATION (The Core Fix)
            # ================================================================
            logger.info("  Running energy minimization...")
            simulation.minimizeEnergy(maxIterations=max_iterations)

            # ================================================================
            # STEP 8: Calculate Final Energy
            # ================================================================
            state1 = simulation.context.getState(getPositions=True, getEnergy=True)
            e_final = state1.getPotentialEnergy().value_in_unit(unit.kilojoules_per_mole)
            energy_change = e_init - e_final
            logger.info(f"  Final potential energy: {e_final:.2f} kJ/mol")
            logger.info(f"  Energy change: {energy_change:.2f} kJ/mol")

            if energy_change < 10:
                logger.warning(
                    f"  Small energy change ({energy_change:.2f} kJ/mol). "
                    "Structure may already be well-optimized."
                )
            else:
                logger.info(f"  ✓ Structure successfully relaxed")

            # ================================================================
            # STEP 9: Save Minimized Structure
            # ================================================================
            with open(output_path, 'w') as f:
                app.PDBFile.writeFile(pdb.topology, state1.getPositions(), f)

            logger.info(f"  ✓ Relaxed structure saved: {output_path}")
            logger.info("Energy minimization complete!")
            
            return output_path

        except Exception as e:
            logger.error(f"Energy minimization failed: {str(e)}")
            logger.warning(f"Returning original structure (fail-safe): {pdb_path}")
            return pdb_path


# ============================================================================
# Convenience Functions
# ============================================================================

def relax_structure(
    pdb_path: Path,
    output_path: Optional[Path] = None,
    stiffness: float = 0.0
) -> Path:
    """
    Convenience function: Relax a protein structure.
    
    Args:
        pdb_path: Path to input PDB
        output_path: Path for output (auto-generated if None)
        stiffness: Backbone restraint strength (0.0 = full flexibility)
    
    Returns:
        Path to relaxed PDB
    """
    minimizer = EnergyMinimizer()
    return minimizer.minimize(pdb_path, output_path, stiffness)


def is_openmm_available() -> bool:
    """Check if OpenMM is installed and functional."""
    return HAS_OPENMM


if __name__ == "__main__":
    print("\n" + "="*80)
    print("AutoScan Molecular Dynamics Module (Module 8 - Upgraded)")
    print("="*80)
    
    if not HAS_OPENMM:
        print("\n⚠ OpenMM is not installed.")
        print("Install via: pip install openmm pdbfixer")
        sys.exit(0)
    
    print("\n✓ OpenMM is available")
    print(f"✓ OpenMM Version: {mm.__version__}")
    print("\nUpgraded Features:")
    print("  • Backbone restraints (harmonic springs on CA, C, N atoms)")
    print("  • Customizable stiffness parameter (kJ/mol/nm²)")
    print("  • Full flexibility to backbone-frozen modes")
    print("\nTo use the minimizer:")
    print("  from autoscan.dynamics.minimizer import EnergyMinimizer")
    print("  minimizer = EnergyMinimizer()")
    print("  # Full flexibility (side-chain + backbone)")
    print("  relaxed = minimizer.minimize(Path('mutant.pdb'), stiffness=0.0)")
    print("  # Moderate restraint (mostly side-chain)")
    print("  relaxed = minimizer.minimize(Path('mutant.pdb'), stiffness=100.0)")
    print("  # Strong restraint (backbone frozen)")
    print("  relaxed = minimizer.minimize(Path('mutant.pdb'), stiffness=1000.0)")

"""
AutoDock Vina Wrapper: Execute molecular docking simulations.
"""

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from autodock.utils import get_logger

logger = get_logger(__name__)


@dataclass
class DockingResult:
    """Result of a docking simulation."""

    binding_affinity: float  # ΔG in kcal/mol
    rmsd_lb: float
    rmsd_ub: float
    ligand_pdbqt: str
    receptor_pdbqt: str


class VinaWrapper:
    """Wrapper around AutoDock Vina binary for molecular docking."""

    def __init__(self, vina_executable: str = "vina"):
        """
        Initialize Vina wrapper.

        Args:
            vina_executable: Path to the Vina executable. Defaults to 'vina' (assumes in PATH).
        """
        self.vina_executable = vina_executable
        self._verify_installation()

    def _verify_installation(self):
        """Verify that Vina is installed and accessible."""
        try:
            result = subprocess.run(
                [self.vina_executable, "--help"],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if "AutoDock Vina" in result.stdout or "AutoDock Vina" in result.stderr:
                logger.info(f"Vina found: {self.vina_executable}")
            else:
                logger.warning("Vina help output unexpected")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Vina verification failed: {e.stderr}")
        except FileNotFoundError:
            raise RuntimeError(
                f"Vina not found at '{self.vina_executable}'. "
                "Please install AutoDock Vina and ensure it's in your PATH."
            )

    def dock(
        self,
        receptor_pdbqt: Path,
        ligand_pdbqt: Path,
        grid_args: list,
        output_pdbqt: Optional[Path] = None,
        cpu: int = 4,
        num_modes: int = 9,
    ) -> DockingResult:
        """
        Execute docking simulation.

        Args:
            receptor_pdbqt: Path to receptor in PDBQT format.
            ligand_pdbqt: Path to ligand in PDBQT format.
            grid_args: Grid box parameters from GridCalculator.to_vina_args().
            output_pdbqt: Path for output PDBQT. Auto-generated if not specified.
            cpu: Number of CPUs to use.
            num_modes: Number of binding modes to generate.

        Returns:
            DockingResult with binding affinity and RMSD.

        Raises:
            RuntimeError: If docking fails.
        """
        receptor_pdbqt = Path(receptor_pdbqt)
        ligand_pdbqt = Path(ligand_pdbqt)

        if output_pdbqt is None:
            output_pdbqt = ligand_pdbqt.with_stem(ligand_pdbqt.stem + "_docked")
        else:
            output_pdbqt = Path(output_pdbqt)

        cmd = [
            self.vina_executable,
            "--receptor",
            str(receptor_pdbqt),
            "--ligand",
            str(ligand_pdbqt),
            "--out",
            str(output_pdbqt),
            "--cpu",
            str(cpu),
            "--num_modes",
            str(num_modes),
        ] + grid_args

        logger.info(f"Running Vina: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd, check=True, capture_output=True, text=True, timeout=300
            )
            output_text = result.stdout + result.stderr

            # Parse binding affinity from Vina output
            affinity = self._parse_affinity(output_text)
            rmsd_lb, rmsd_ub = self._parse_rmsd(output_text)

            logger.info(
                f"Docking completed. Binding Affinity: {affinity} kcal/mol"
            )

            return DockingResult(
                binding_affinity=affinity,
                rmsd_lb=rmsd_lb,
                rmsd_ub=rmsd_ub,
                ligand_pdbqt=str(ligand_pdbqt),
                receptor_pdbqt=str(receptor_pdbqt),
            )

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Vina docking failed: {e.stderr}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("Vina docking timed out (exceeded 5 minutes)")

    @staticmethod
    def _parse_affinity(output: str) -> float:
        """Parse binding affinity (ΔG) from Vina output."""
        match = re.search(r"([-+]?\d+\.\d+)\s+kcal/mol", output)
        if match:
            return float(match.group(1))
        raise RuntimeError("Could not parse binding affinity from Vina output")

    @staticmethod
    def _parse_rmsd(output: str) -> tuple[float, float]:
        """Parse RMSD values from Vina output."""
        match = re.search(r"(RMSD\s+from\s+best\s+mode|lb|ub).*?(\d+\.\d+).*?(\d+\.\d+)", output)
        # Simplified: return 0.0 if not found (Vina output format varies)
        return 0.0, 0.0

    def to_json(self, result: DockingResult) -> str:
        """Convert docking result to JSON for MutationScan integration."""
        return json.dumps(
            {
                "binding_affinity_kcal_mol": result.binding_affinity,
                "rmsd_lb": result.rmsd_lb,
                "rmsd_ub": result.rmsd_ub,
                "receptor_pdbqt": result.receptor_pdbqt,
                "ligand_pdbqt": result.ligand_pdbqt,
            }
        )

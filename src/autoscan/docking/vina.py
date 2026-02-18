"""Vina engine wrapper for CLI usage."""

from pathlib import Path
from typing import Optional

from autoscan.docking.utils import calculate_grid_box
from autoscan.engine.vina import VinaWrapper


class VinaEngine:
    """Minimal Vina engine wrapper for the CLI."""

    def __init__(self, receptor_pdbqt: str, ligand_pdbqt: str, vina_executable: str = "vina"):
        self.receptor_pdbqt = Path(receptor_pdbqt)
        self.ligand_pdbqt = Path(ligand_pdbqt)
        self.vina = VinaWrapper(vina_executable=vina_executable)

    def run(
        self,
        center: list,
        ligand_mol=None,
        buffer_angstroms: float = 6.0,
        cpu: int = 4,
        num_modes: int = 9,
        exhaustiveness: int = 8,
        output_pdbqt: Optional[str] = None,
        use_consensus: bool = False,
        consensus_method: str = "mean",
        flex_pdbqt: Optional[Path] = None,
    ):
        """
        Run Vina docking.

        Args:
            center: [x, y, z] center coordinates.
            ligand_mol: Optional ligand molecule for dynamic box sizing.
            buffer_angstroms: Padding around ligand (default 6.0 Å).
            cpu: Number of CPUs (default 4).
            num_modes: Number of binding modes (default 9).
            exhaustiveness: Search exhaustiveness (default 8, use 32 for deep search).
            output_pdbqt: Output file path.

        Returns:
            Binding affinity in kcal/mol.
        """
        grid = calculate_grid_box(center, ligand_mol=ligand_mol, buffer_angstroms=buffer_angstroms)
        grid_args = [
            "--center_x",
            str(grid["center_x"]),
            "--center_y",
            str(grid["center_y"]),
            "--center_z",
            str(grid["center_z"]),
            "--size_x",
            str(grid["size_x"]),
            "--size_y",
            str(grid["size_y"]),
            "--size_z",
            str(grid["size_z"]),
        ]

        result = self.vina.dock(
            self.receptor_pdbqt,
            self.ligand_pdbqt,
            grid_args,
            output_pdbqt=output_pdbqt,
            cpu=cpu,
            num_modes=num_modes,
            exhaustiveness=exhaustiveness,
            use_consensus=use_consensus,
            consensus_method=consensus_method,
            flex_pdbqt=flex_pdbqt,
        )
        return result

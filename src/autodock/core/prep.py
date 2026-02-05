"""
Preparation module: Convert PDB to PDBQT using OpenBabel.
Also handles in silico mutagenesis using BioPython.
"""

import subprocess
from pathlib import Path
from typing import Optional

from Bio import PDB

from autodock.utils import get_logger

logger = get_logger(__name__)


class PrepareVina:
    """Prepare molecules for AutoDock Vina by converting to PDBQT format and mutating residues."""

    @staticmethod
    def pdb_to_pdbqt(pdb_file: Path, output_file: Optional[Path] = None) -> Path:
        """
        Convert PDB file to PDBQT using OpenBabel.

        Args:
            pdb_file: Path to input PDB file.
            output_file: Path to output PDBQT file. If None, replaces .pdb with .pdbqt.

        Returns:
            Path to the output PDBQT file.

        Raises:
            RuntimeError: If obabel conversion fails.
        """
        pdb_file = Path(pdb_file)

        if output_file is None:
            output_file = pdb_file.with_suffix(".pdbqt")
        else:
            output_file = Path(output_file)

        logger.info(f"Converting {pdb_file} to PDBQT")

        try:
            result = subprocess.run(
                ["obabel", str(pdb_file), "-O", str(output_file), "-xr"],
                check=True,
                capture_output=True,
                text=True,
            )
            logger.info(f"Successfully converted to: {output_file}")
            return output_file
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"OpenBabel conversion failed: {e.stderr}")
        except FileNotFoundError:
            raise RuntimeError(
                "obabel not found. Please install OpenBabel via apt-get or conda."
            )

    @staticmethod
    def mutate_residue(
        pdb_file: Path, chain_id: str, residue_num: int, new_aa: str
    ) -> Path:
        """
        Mutate a residue in a PDB structure in silico using BioPython.

        Args:
            pdb_file: Path to input PDB file.
            chain_id: Chain identifier (e.g., "A").
            residue_num: Residue number to mutate.
            new_aa: New amino acid (3-letter or 1-letter code, e.g., "GLY" or "G").

        Returns:
            Path to the mutated PDB file (saved as _mutant.pdb).

        Raises:
            RuntimeError: If mutation fails.
        """
        pdb_file = Path(pdb_file)
        output_file = pdb_file.with_stem(pdb_file.stem + "_mutant")

        # Convert 1-letter to 3-letter code if needed
        aa_3_to_1 = {
            "ALA": "A",
            "ARG": "R",
            "ASN": "N",
            "ASP": "D",
            "CYS": "C",
            "GLN": "Q",
            "GLU": "E",
            "GLY": "G",
            "HIS": "H",
            "ILE": "I",
            "LEU": "L",
            "LYS": "K",
            "MET": "M",
            "PHE": "F",
            "PRO": "P",
            "SER": "S",
            "THR": "T",
            "TRP": "W",
            "TYR": "Y",
            "VAL": "V",
        }
        aa_1_to_3 = {v: k for k, v in aa_3_to_1.items()}

        new_aa_3 = aa_1_to_3.get(new_aa.upper(), new_aa.upper())

        logger.info(
            f"Mutating {pdb_file}: Chain {chain_id}, Res {residue_num} -> {new_aa_3}"
        )

        try:
            parser = PDB.PDBParser(QUIET=True)
            structure = parser.get_structure("protein", str(pdb_file))

            chain = structure[0][chain_id]
            residue = chain[residue_num]

            # Replace residue with new amino acid
            residue.resname = new_aa_3

            writer = PDB.PPBuilder()
            io = PDB.PDBIO()
            io.set_structure(structure)
            io.save(str(output_file))

            logger.info(f"Mutated structure saved to: {output_file}")
            return output_file
        except Exception as e:
            raise RuntimeError(f"Mutation failed: {e}")

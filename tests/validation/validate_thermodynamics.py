"""
Specificity benchmark for AutoScan using 2XCT (ciprofloxacin vs benzene).
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from Bio.PDB import PDBIO, PDBList, PDBParser, Select
from rdkit import Chem
from rdkit.Chem import AllChem

from autoscan.core import PrepareVina
from autoscan.engine import GridCalculator, VinaWrapper


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RECEPTOR_DIR = DATA_DIR / "receptors"
LIGAND_DIR = DATA_DIR / "ligands"
OUTPUT_DIR = Path(__file__).resolve().parent / "output_thermo"

PDB_ID = "2XCT"
LIGAND_RESNAME = "CPF"
CHAINS = {"A", "B"}
POCKET_NAME = "GyrA_pocket"


class ProteinSelect(Select):
    def accept_chain(self, chain):
        return chain.id in CHAINS

    def accept_residue(self, residue):
        return residue.id[0] == " "


class LigandSelect(Select):
    def __init__(self, chain_id: str, residue_id):
        self.chain_id = chain_id
        self.residue_id = residue_id

    def accept_chain(self, chain):
        return chain.id == self.chain_id

    def accept_residue(self, residue):
        return residue.id == self.residue_id


def fetch_pdb(pdb_id: str, output_path: Path) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RECEPTOR_DIR.mkdir(parents=True, exist_ok=True)
    pdbl = PDBList()
    downloaded = pdbl.retrieve_pdb_file(pdb_id, pdir=str(OUTPUT_DIR), file_format="pdb")
    downloaded_path = Path(downloaded)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(downloaded_path, output_path)
    return output_path


def split_structure(pdb_path: Path, receptor_out: Path, ligand_out: Path) -> None:
    parser = PDBParser(QUIET=True)
    structure = parser.get_structure(PDB_ID, str(pdb_path))

    ligand_chain_id = None
    ligand_residue_id = None
    for chain in structure.get_chains():
        for residue in chain:
            if residue.id[0] != " " and residue.resname == LIGAND_RESNAME:
                ligand_chain_id = chain.id
                ligand_residue_id = residue.id
                break
        if ligand_chain_id is not None:
            break

    if ligand_chain_id is None:
        raise RuntimeError(f"Ligand {LIGAND_RESNAME} not found in {pdb_path}")

    io = PDBIO()
    io.set_structure(structure)
    io.save(str(receptor_out), ProteinSelect())
    io.save(str(ligand_out), LigandSelect(ligand_chain_id, ligand_residue_id))


def build_benzene(output_path: Path) -> None:
    mol = Chem.MolFromSmiles("c1ccccc1")
    mol = Chem.AddHs(mol)
    AllChem.EmbedMolecule(mol, randomSeed=7)
    AllChem.UFFOptimizeMolecule(mol)
    Chem.MolToPDBFile(mol, str(output_path))


def dock_ligand(
    vina: VinaWrapper,
    receptor_pdbqt: Path,
    ligand_pdbqt: Path,
    grid_calc: GridCalculator,
) -> float:
    grid_box = grid_calc.get_grid(POCKET_NAME)
    result = vina.dock(
        receptor_pdbqt,
        ligand_pdbqt,
        grid_box.to_vina_args(),
        num_modes=1,
    )
    return result.binding_affinity


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    missing = []
    if shutil.which("obabel") is None:
        missing.append("obabel (OpenBabel)")
    if shutil.which("autoscan-vina") is None:
        missing.append("autoscan-vina")
    if missing:
        print("Missing required system tools:")
        for tool in missing:
            print(f"- {tool}")
        print("Install them and re-run this validation script.")
        sys.exit(1)

    receptor_ref = OUTPUT_DIR / "receptor_ref.pdb"
    ligand_cipro = OUTPUT_DIR / "ciprofloxacin_ref.pdb"
    ligand_benzene = OUTPUT_DIR / "benzene_ref.pdb"
    receptor_pdbqt = OUTPUT_DIR / "receptor_ref.pdbqt"
    cipro_pdbqt = OUTPUT_DIR / "ciprofloxacin.pdbqt"
    benzene_pdbqt = OUTPUT_DIR / "benzene.pdbqt"

    pdb_path = RECEPTOR_DIR / f"{PDB_ID}_orig.pdb"
    if not pdb_path.exists():
        pdb_path = RECEPTOR_DIR / f"{PDB_ID}.pdb"
        if not pdb_path.exists():
            pdb_path = fetch_pdb(PDB_ID, pdb_path)

    split_structure(pdb_path, receptor_ref, ligand_cipro)
    build_benzene(ligand_benzene)

    prep = PrepareVina(use_meeko=True, ph=7.4)
    prep.pdb_to_pdbqt(receptor_ref, receptor_pdbqt, molecule_type="receptor")
    prep.pdb_to_pdbqt(ligand_cipro, cipro_pdbqt, molecule_type="ligand")
    prep.pdb_to_pdbqt(ligand_benzene, benzene_pdbqt, molecule_type="ligand")

    grid_calc = GridCalculator(str(ROOT / "config" / "pockets.yaml"))
    vina = VinaWrapper()

    cipro_affinity = dock_ligand(vina, receptor_pdbqt, cipro_pdbqt, grid_calc)
    benzene_affinity = dock_ligand(vina, receptor_pdbqt, benzene_pdbqt, grid_calc)

    delta_g = benzene_affinity - cipro_affinity

    print(f"Ciprofloxacin affinity: {cipro_affinity:.3f} kcal/mol")
    print(f"Benzene affinity: {benzene_affinity:.3f} kcal/mol")
    print(f"Delta Delta G (Benzene - Cipro): {delta_g:.3f} kcal/mol")

    pass_cipro = cipro_affinity < -8.0
    pass_benzene = benzene_affinity > -5.5
    pass_delta = delta_g >= 2.5

    if pass_cipro and pass_benzene and pass_delta:
        print("PASS")
    else:
        print("FAIL")


if __name__ == "__main__":
    main()

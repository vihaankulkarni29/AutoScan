import os
from Bio.PDB import PDBParser

FILES = ["1SQN", "1OQA", "4DJU", "2XCT"]
DATA_DIR = "tests/benchmark_data"


def inspect() -> None:
    parser = PDBParser(QUIET=True)

    print(f"{'PDB':<6} | {'Residues Found (Unique HETATMs)'}")
    print("-" * 60)

    for pdb_id in FILES:
        path = os.path.join(DATA_DIR, f"{pdb_id}.pdb")
        if not os.path.exists(path):
            print(f"{pdb_id:<6} | ERROR: File not found")
            continue

        structure = parser.get_structure(pdb_id, path)
        hetatms = set()

        for residue in structure.get_residues():
            if residue.id[0] != " ":
                resname = residue.get_resname().strip()
                hetatms.add(resname)

        print(f"{pdb_id:<6} | {', '.join(sorted(hetatms))}")


if __name__ == "__main__":
    inspect()

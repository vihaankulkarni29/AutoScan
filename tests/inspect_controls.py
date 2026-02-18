#!/usr/bin/env python
"""
PDB Autopsy: Inspect actual HETATM residues in benchmark PDB files.
Determines correct ligand residue names for the control study.
"""

import os
from Bio.PDB import PDBParser

# The problematic files from your control set
FILES = ["1AID", "2J7E", "1TNH", "1STP", "3PTB", "1HVR", "1OYT"]
DATA_DIR = "tests/benchmark_data"

def inspect():
    parser = PDBParser(QUIET=True)
    print(f"{'PDB':<8} | {'HETATM Residues Found':<50}")
    print("-" * 70)
    
    for pdb_id in FILES:
        path = os.path.join(DATA_DIR, f"{pdb_id}.pdb")
        if not os.path.exists(path):
            print(f"{pdb_id:<8} | ❌ File not found in {DATA_DIR}")
            continue
            
        try:
            structure = parser.get_structure(pdb_id, path)
            hetatms = set()
            
            for residue in structure.get_residues():
                # Look for non-standard residues (HETATMs)
                resname = residue.get_resname().strip()
                # HETATMs have a non-space first character in their ID
                is_hetatm = residue.id[0] != " "
                
                if is_hetatm and resname not in ['HOH', 'WAT', 'CL', 'NA', 'MG', 'CA', 'ZN']:
                    hetatms.add(f"{resname}")
            
            if hetatms:
                print(f"{pdb_id:<8} | {', '.join(sorted(hetatms))}")
            else:
                print(f"{pdb_id:<8} | ⚠️  No ligands found (water/ions only)")
        except Exception as e:
            print(f"{pdb_id:<8} | ❌ Error: {str(e)[:40]}")

if __name__ == "__main__":
    inspect()

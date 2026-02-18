import typer
from pathlib import Path
import math
import json
import tempfile
import shutil
from datetime import datetime
from typing import Optional

from autoscan.docking.vina import VinaEngine
from autoscan.core.prep import PrepareVina
from autoscan.utils.dependency_check import ensure_dependencies
from autoscan.utils.error_handler import ErrorHandler

app = typer.Typer()
console = ErrorHandler() # The Robustness Layer


def validate_pdbqt_file(filepath: str, field_name: str) -> Path:
    """
    Validate that a file exists and has .pdbqt extension.
    
    Args:
        filepath: Path to the file
        field_name: Name for error messages (e.g., "Receptor", "Ligand")
    
    Returns:
        Path object if valid
    
    Raises:
        typer.BadParameter: If file is invalid or missing
    """
    path = Path(filepath)
    
    # Check if file exists
    if not path.exists():
        raise typer.BadParameter(
            f"{field_name} file does not exist: {filepath}",
            param_hint=f"--{field_name.lower()}"
        )
    
    # Check if it's a file (not a directory)
    if not path.is_file():
        raise typer.BadParameter(
            f"{field_name} path is not a file: {filepath}",
            param_hint=f"--{field_name.lower()}"
        )
    
    # Check file extension
    if path.suffix.lower() != ".pdbqt":
        raise typer.BadParameter(
            f"{field_name} must be a .pdbqt file, got: {path.suffix}",
            param_hint=f"--{field_name.lower()}"
        )
    
    return path


def validate_coordinates(center_x: float, center_y: float, center_z: float) -> None:
    """
    Validate that coordinates are valid floats (not NaN or Inf).
    
    Args:
        center_x, center_y, center_z: Coordinate values
    
    Raises:
        typer.BadParameter: If any coordinate is invalid
    """
    coords = {"center_x": center_x, "center_y": center_y, "center_z": center_z}
    
    for name, value in coords.items():
        if math.isnan(value) or math.isinf(value):
            raise typer.BadParameter(
                f"{name} must be a valid number, got: {value}",
                param_hint=f"--{name}"
            )


def parse_mutation_string(mutation_str: str) -> tuple:
    """
    Parse mutation string in format: CHAIN:RESIDUE:FROM_AA:TO_AA
    
    Example: A:87:D:G (Chain A, Residue 87, Asp to Gly)
    
    Args:
        mutation_str: Mutation specification string
    
    Returns:
        Tuple of (chain_id, residue_num, from_aa, to_aa)
    
    Raises:
        typer.BadParameter: If format is invalid
    """
    try:
        parts = mutation_str.split(":")
        if len(parts) != 4:
            raise ValueError("Expected format: CHAIN:RESIDUE:FROM_AA:TO_AA")
        
        chain_id = parts[0]
        residue_num = int(parts[1])
        from_aa = parts[2]
        to_aa = parts[3]
        
        return chain_id, residue_num, from_aa, to_aa
    except (ValueError, IndexError) as e:
        raise typer.BadParameter(
            f"Invalid mutation format. Expected: CHAIN:RESIDUE:FROM_AA:TO_AA (e.g., A:87:D:G). Got: {mutation_str}",
            param_hint="--mutation"
        )


def convert_pdb_to_pdbqt(pdb_file: Path) -> Path:
    """
    Convert PDB file to PDBQT using PrepareVina.
    
    Args:
        pdb_file: Path to PDB file
    
    Returns:
        Path to converted PDBQT file
    
    Raises:
        typer.BadParameter: If conversion fails
    """
    try:
        prep = PrepareVina(use_meeko=True, ph=7.4)
        pdbqt_file = prep.pdb_to_pdbqt(
            str(pdb_file),
            output_file=str(pdb_file.with_suffix(".pdbqt")),
            add_waters=False,
            add_hydrogens=True
        )
        return Path(pdbqt_file)
    except Exception as e:
        raise typer.BadParameter(
            f"Failed to convert PDB to PDBQT: {str(e)}",
            param_hint="--receptor"
        )


def save_results_json(results: dict, output_file: Path) -> None:
    """Save docking results to JSON file."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    console.log(f"✓ Results saved to: {output_file}")




@app.command()
def dock(
    receptor: str = typer.Option(..., help="Path to Receptor (PDB or PDBQT)", metavar="RECEPTOR"),
    ligand: str = typer.Option(..., help="Path to Ligand (PDB or PDBQT)", metavar="LIGAND"),
    center_x: float = typer.Option(..., help="Binding pocket center X coordinate", metavar="X"),
    center_y: float = typer.Option(..., help="Binding pocket center Y coordinate", metavar="Y"),
    center_z: float = typer.Option(..., help="Binding pocket center Z coordinate", metavar="Z"),
    mutation: Optional[str] = typer.Option(None, help="Mutation: CHAIN:RESIDUE:FROM_AA:TO_AA (e.g., A:87:D:G)", metavar="MUTATION"),
    output: Optional[str] = typer.Option(None, help="Output file for results (JSON format)", metavar="OUTPUT.json"),
    use_consensus: bool = typer.Option(False, "--use-consensus/--no-consensus", help="Enable consensus scoring from multiple docking engines"),
    consensus_method: str = typer.Option("mean", help="Consensus method: mean, median, or weighted", metavar="METHOD"),
    flex: Optional[str] = typer.Option(None, help="Path to flexible side-chain PDBQT for flexible docking", metavar="FLEX.pdbqt")
):
    """
    Run the AutoScan Docking Protocol.
    
    Supports both PDB and PDBQT formats. PDB files are automatically converted to PDBQT.
    Optional in-silico mutagenesis for resistance and selectivity studies.

    Examples:
        Standard docking with PDBQT files:
        $ autoscan dock --receptor protein.pdbqt --ligand drug.pdbqt \\
            --center-x 10.5 --center-y 20.3 --center-z 15.8

        With PDB input (auto-converted):
        $ autoscan dock --receptor protein.pdb --ligand drug.pdb \\
            --center-x 10.5 --center-y 20.3 --center-z 15.8

        With mutation (resistance study):
        $ autoscan dock --receptor protein.pdb --ligand drug.pdb \\
            --center-x 10.5 --center-y 20.3 --center-z 15.8 \\
            --mutation A:87:D:G --output result.json
    """
    try:
        console.log("="*80)
        console.log("Initializing AutoScan Docking Module...")
        console.log("="*80)

        # ====== INPUT VALIDATION (Integrity Check) ======
        console.log("\n[1/4] Validating Input Files...")
        receptor_path = Path(receptor)
        ligand_path = Path(ligand)
        
        # Check existence
        if not receptor_path.exists():
            raise typer.BadParameter(
                f"Receptor file does not exist: {receptor}",
                param_hint="--receptor"
            )
        if not ligand_path.exists():
            raise typer.BadParameter(
                f"Ligand file does not exist: {ligand}",
                param_hint="--ligand"
            )
        
        # Convert PDB to PDBQT if needed
        if receptor_path.suffix.lower() == ".pdb":
            console.log("  Converting receptor PDB → PDBQT...")
            receptor_path = convert_pdb_to_pdbqt(receptor_path)
        elif receptor_path.suffix.lower() != ".pdbqt":
            raise typer.BadParameter(
                f"Receptor must be .pdb or .pdbqt, got: {receptor_path.suffix}",
                param_hint="--receptor"
            )
        
        if ligand_path.suffix.lower() == ".pdb":
            console.log("  Converting ligand PDB → PDBQT...")
            ligand_path = convert_pdb_to_pdbqt(ligand_path)
        elif ligand_path.suffix.lower() != ".pdbqt":
            raise typer.BadParameter(
                f"Ligand must be .pdb or .pdbqt, got: {ligand_path.suffix}",
                param_hint="--ligand"
            )
        
        # Handle mutations if specified
        if mutation:
            console.log(f"\n  Applying mutation: {mutation}...")
            chain_id, residue_num, from_aa, to_aa = parse_mutation_string(mutation)
            
            # Read original PDB (before PDBQT conversion)
            original_pdb = Path(receptor).with_suffix(".pdb")
            if not original_pdb.exists():
                raise typer.BadParameter(
                    f"Cannot apply mutation: original PDB file not found. Expected: {original_pdb}",
                    param_hint="--mutation"
                )
            
            # Apply mutation to PDB
            prep = PrepareVina()
            mutant_pdb = prep.mutate_residue(original_pdb, chain_id, residue_num, to_aa)
            
            # Convert mutant PDB to PDBQT
            receptor_path = convert_pdb_to_pdbqt(mutant_pdb)
            console.log(f"  ✓ Mutation applied: {receptor_path}")
        
        console.log("\n[2/4] Validating Coordinates...")
        validate_coordinates(center_x, center_y, center_z)
        
        console.log("\n✓ Receptor: " + str(receptor_path))
        console.log("✓ Ligand:   " + str(ligand_path))
        console.log(f"✓ Center:   ({center_x}, {center_y}, {center_z})")
        if mutation:
            console.log(f"✓ Mutation: {mutation}")
        if use_consensus:
            console.log(f"✓ Consensus Scoring: Enabled ({consensus_method})")
        if flex:
            console.log(f"✓ Flexible Docking: {flex}")

        console.log("\n[3/4] Checking Dependencies...")
        ensure_dependencies()

        console.log("\n[4/4] Running Docking Engine...")
        
        # Validate flex file if provided
        flex_path = None
        if flex:
            flex_path = Path(flex)
            if not flex_path.exists():
                raise typer.BadParameter(
                    f"Flexible residues file does not exist: {flex}",
                    param_hint="--flex"
                )
            if flex_path.suffix.lower() != ".pdbqt":
                raise typer.BadParameter(
                    f"Flex file must be .pdbqt, got: {flex_path.suffix}",
                    param_hint="--flex"
                )
        
        engine = VinaEngine(str(receptor_path), str(ligand_path))
        docking_result = engine.run(
            center=[center_x, center_y, center_z],
            use_consensus=use_consensus,
            consensus_method=consensus_method,
            flex_pdbqt=flex_path
        )

        # Prepare results
        results = {
            "timestamp": datetime.now().isoformat(),
            "receptor": str(receptor_path),
            "ligand": str(ligand_path),
            "binding_affinity_kcal_mol": float(docking_result.binding_affinity),
            "center": {
                "x": center_x,
                "y": center_y,
                "z": center_z
            },
            "mutation": mutation if mutation else "WT"
        }
        
        # Add consensus scores if available
        if use_consensus and docking_result.consensus_affinity is not None:
            results["consensus_mode"] = True
            results["consensus_affinity_kcal_mol"] = float(docking_result.consensus_affinity)
            results["consensus_uncertainty_kcal_mol"] = float(docking_result.consensus_uncertainty)
            results["individual_scores"] = docking_result.consensus_scores
            success_msg = f"Docking Complete! Consensus Affinity: {docking_result.consensus_affinity:.2f} ± {docking_result.consensus_uncertainty:.2f} kcal/mol"
        else:
            results["consensus_mode"] = False
            success_msg = f"Docking Complete! Binding Affinity: {docking_result.binding_affinity:.2f} kcal/mol"
        
        # Save results if output specified
        if output:
            save_results_json(results, Path(output))
        
        console.success(f"\n{success_msg}")
        console.log("="*80)

    except typer.BadParameter:
        # Re-raise Typer validation errors (will show clean error message)
        raise
    except Exception as e:
        console.error(f"Docking Failed: {str(e)}")
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()





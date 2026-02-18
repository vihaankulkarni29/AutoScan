import typer
from pathlib import Path
import math

from autoscan.docking.vina import VinaEngine
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


@app.command()
def dock(
    receptor: str = typer.Option(..., help="Path to Receptor PDBQT", metavar="RECEPTOR.pdbqt"),
    ligand: str = typer.Option(..., help="Path to Ligand PDBQT", metavar="LIGAND.pdbqt"),
    center_x: float = typer.Option(..., help="Binding pocket center X coordinate", metavar="X"),
    center_y: float = typer.Option(..., help="Binding pocket center Y coordinate", metavar="Y"),
    center_z: float = typer.Option(..., help="Binding pocket center Z coordinate", metavar="Z")
):
    """
    Run the AutoScan Docking Protocol.
    
    Example:
        autoscan dock --receptor protein.pdbqt --ligand drug.pdbqt \\
            --center-x 10.5 --center-y 20.3 --center-z 15.8
    """
    try:
        console.log("="*80)
        console.log("Initializing AutoScan Docking Module...")
        console.log("="*80)

        # ====== INPUT VALIDATION (Integrity Check) ======
        console.log("\n[1/4] Validating Input Files...")
        receptor_path = validate_pdbqt_file(receptor, "Receptor")
        ligand_path = validate_pdbqt_file(ligand, "Ligand")
        
        console.log("[2/4] Validating Coordinates...")
        validate_coordinates(center_x, center_y, center_z)
        
        console.log("\n✓ Receptor: " + str(receptor_path))
        console.log("✓ Ligand:   " + str(ligand_path))
        console.log(f"✓ Center:   ({center_x}, {center_y}, {center_z})")

        console.log("\n[3/4] Checking Dependencies...")
        ensure_dependencies()

        # Physics Check (Grid Box)
        # Note: In a real run, you'd load the ligand to calculate size
        # For CLI, we pass explicit center, but logic handles size internally

        console.log("\n[4/4] Running Docking Engine...")
        engine = VinaEngine(str(receptor_path), str(ligand_path))
        score = engine.run(center=[center_x, center_y, center_z])

        console.success(f"\nDocking Complete! Binding Affinity: {score} kcal/mol")
        console.log("="*80)

    except typer.BadParameter:
        # Re-raise Typer validation errors (will show clean error message)
        raise
    except Exception as e:
        console.error(f"Docking Failed: {str(e)}")
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()





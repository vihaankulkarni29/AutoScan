"""Simple console error handling for the CLI."""

import sys


class ErrorHandler:
    """Lightweight logging helper for CLI output."""

    def __init__(self, quiet: bool = False):
        self.quiet = quiet

    def log(self, message: str) -> None:
        if not self.quiet:
            print(message)

    def warn(self, message: str) -> None:
        """Print a warning message to stdout."""
        print(f"{message}")

    def success(self, message: str) -> None:
        print(f"[OK] {message}")

    def error(self, message: str) -> None:
        print(f"[ERROR] {message}", file=sys.stderr)

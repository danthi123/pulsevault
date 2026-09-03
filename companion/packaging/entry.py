"""PyInstaller entry point — packaged as the pulsevault-companion binary."""
from pulsevault_companion.cli import main

if __name__ == "__main__":
    raise SystemExit(main())

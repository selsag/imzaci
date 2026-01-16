"""
Entry point for PDF İmzacı application.

This module serves as the main entry point when running the application
as a Python module (python -m imzaci) or when packaged with PyInstaller.

Usage:
    python -m imzaci              # Run GUI
    python gui.py                 # Direct execution
"""

import sys
from pathlib import Path

# Ensure the application directory is in the Python path
app_dir = Path(__file__).parent
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))

# Import and launch the GUI application
try:
    from gui import ModernTTKApp
    
    if __name__ == "__main__":
        app = ModernTTKApp()
        app.root.mainloop()
        
except ImportError as e:
    print(f"Error: Failed to import GUI module.\n{e}")
    print("Please ensure all dependencies are installed:")
    print("  pip install -r requirements.txt")
    sys.exit(1)
except Exception as e:
    print(f"Error: Failed to start application.\n{e}")
    sys.exit(1)

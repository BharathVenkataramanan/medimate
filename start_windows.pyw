"""Optional windowed Python launcher for MediMate on Windows.

This is plain, inspectable Python and requires a standard Python installation
with .pyw file association. No executable bundler, PowerShell bootstrap, or
elevation is used.
"""
from pathlib import Path
import os
import sys
import traceback

os.chdir(Path(__file__).resolve().parent)

try:
    from start_review import main
    main()
except BaseException as exc:
    try:
        from tkinter import Tk, messagebox
        root = Tk()
        root.withdraw()
        messagebox.showerror("MediMate startup", f"{exc}\n\nRun 'py -3 -B start_windows.py' in PowerShell for diagnostics.")
        root.destroy()
    except Exception:
        traceback.print_exc()
    sys.exit(1)

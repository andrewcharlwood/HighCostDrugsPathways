"""One-time dev setup: adds src/ to the venv's Python path via a .pth file."""

import site
import sys
from pathlib import Path

src_dir = Path(__file__).resolve().parent / "src"
site_packages = Path(site.getsitepackages()[-1])
pth_file = site_packages / "patient_pathways.pth"

pth_file.write_text(str(src_dir) + "\n")
print(f"Created {pth_file}")
print(f"  -> {src_dir}")

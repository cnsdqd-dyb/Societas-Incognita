"""Render the current README population gallery and typed work previews."""
import subprocess
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent

def main():
    for name in ["render_population_gallery.py", "render_artwork_showcase.py"]:
        subprocess.run([sys.executable, "-u", "-X", "utf8", str(HERE/name)],check=True)

if __name__=="__main__":main()

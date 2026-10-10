"""Run/resume only the explicitly bounded native functional diagnostic."""
import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    root = Path(args.run).resolve()
    sys.path.insert(0, str(root/'engine_snapshot'))
    from functional_pilot_admission import install
    install(root)
    import native_codex
    native_codex.main()


if __name__ == '__main__': main()

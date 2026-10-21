"""Compatibility CLI: compile canonical modules, never package dev shims."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_submission import main
if __name__=='__main__':
    if '--output' not in sys.argv: sys.argv.extend(['--output',str(ROOT/'dist/solution.zip')])
    main()

"""
Experiments package containing ablation studies and baseline comparisons.
Enables running experiment modules directly from repo root:
python -m experiments.<name>
"""
import os
import sys

# Ensure src/ and repo root are in sys.path for submodule execution
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_src_dir = os.path.join(_repo_root, "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

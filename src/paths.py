"""
Central repository path definitions.
All paths are resolved relative to REPO_ROOT so that all library modules,
pipelines, studies, tests, and tools function identically regardless of the
current working directory.
"""
import os
from pathlib import Path

# Repository Root (parent of src/)
REPO_ROOT = Path(__file__).resolve().parent.parent

# Primary Top-Level Directories
SRC = REPO_ROOT / "src"
EXPERIMENTS = REPO_ROOT / "experiments"
EXP_MODELS = EXPERIMENTS / "models"
TOOLS = REPO_ROOT / "tools"
TESTS = REPO_ROOT / "tests"
MODELS = REPO_ROOT / "models"
PLOTS = REPO_ROOT / "plots"
DOCS = REPO_ROOT / "docs"
REPORTS = REPO_ROOT / "reports"
ARCHIVE = REPO_ROOT / "archive"

# Structured Data Subdirectories
DATA = REPO_ROOT / "data"
DATASETS = DATA / "datasets"
RESULTS = DATA / "results"
AUDITS = DATA / "audits"
RAW = DATA / "raw"

# Manifest Path
RUN_MANIFEST = REPO_ROOT / "run_manifest.json"

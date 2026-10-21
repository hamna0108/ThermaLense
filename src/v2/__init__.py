"""V2 Module Wrappers for Week 6.

Frozen modules in src/ stay completely untouched.
All V2 architectural improvements (sigma estimation, goodness-of-fit gating,
range guards, declared physics inversion, and limitation guards) are implemented
here as modular, non-destructive wrappers.
"""

from src.v2.sigma_estimator import estimate_sigma_from_baseline
from src.v2.gof_gate import evaluate_goodness_of_fit
from src.v2.range_guard import range_guarded_mode3_inversion
from src.v2.declared_physics import invert_with_declared_physics

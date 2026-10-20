import os
import torch
import numpy as np
import pytest
from src.paths import MODELS, DATASETS
from src.models.fno2d import FNO2d

def test_fno_mask_mechanics():
    """
    Test the fundamental mechanics of use_hard_mask flag in FNO2d.
    - True: all 4 boundaries (dim 2 index 0/-1, dim 3 index 0/-1) must be strictly 0.0.
    - False: boundaries must not be identically zeroed.
    """
    torch.manual_seed(42)
    x = torch.randn(2, 3, 64, 64)
    
    # Masked FNO
    fno_masked = FNO2d(modes1=8, modes2=8, width=16, use_hard_mask=True)
    out_masked = fno_masked(x)
    
    assert torch.all(out_masked[:, :, 0, :] == 0.0), "Masked FNO must zero row 0"
    assert torch.all(out_masked[:, :, -1, :] == 0.0), "Masked FNO must zero row -1"
    assert torch.all(out_masked[:, :, :, 0] == 0.0), "Masked FNO must zero col 0"
    assert torch.all(out_masked[:, :, :, -1] == 0.0), "Masked FNO must zero col -1"
    
    # Unmasked FNO
    fno_unmasked = FNO2d(modes1=8, modes2=8, width=16, use_hard_mask=False)
    out_unmasked = fno_unmasked(x)
    
    assert not torch.all(out_unmasked[:, :, 0, :] == 0.0), "Unmasked FNO must not zero row 0"
    assert not torch.all(out_unmasked[:, :, -1, :] == 0.0), "Unmasked FNO must not zero row -1"
    assert not torch.all(out_unmasked[:, :, :, 0] == 0.0), "Unmasked FNO must not zero col 0"
    assert not torch.all(out_unmasked[:, :, :, -1] == 0.0), "Unmasked FNO must not zero col -1"

def test_heat_fno_unmasked_weights_inference():
    """
    Test that the frozen heat surrogate model (fno2d_heat.pt) runs unmasked
    and accurately preserves non-zero initial conditions at t=0.
    """
    ckpt_path = MODELS / "fno2d_heat.pt"
    assert os.path.exists(ckpt_path), f"Checkpoint missing: {ckpt_path}"
    
    ckpt = torch.load(ckpt_path, map_location="cpu")
    # Verify metadata flag
    assert ckpt.get("use_hard_mask", False) is False, "Heat FNO checkpoint must be flagged use_hard_mask=False"
    
    model = FNO2d(modes1=16, modes2=12, width=32, use_hard_mask=False)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    
    # Test on test_interpolation sample 0
    data = np.load(DATASETS / "test_interpolation.npz")
    u_true = data["u"][0]  # shape (100, 50)
    alpha_0 = data["alpha"][0]
    x_np, t_np = data["x"], data["t"]
    
    lm, ls = ckpt["log_alpha_mean"].item(), ckpt["log_alpha_std"].item()
    t_mesh, x_mesh = np.meshgrid(t_np, x_np, indexing="ij")
    t_tensor = torch.tensor(2 * t_mesh - 1, dtype=torch.float32)
    x_tensor = torch.tensor(2 * x_mesh - 1, dtype=torch.float32)
    a_sc = (np.log10(alpha_0) - lm) / ls
    x_in = torch.stack([t_tensor, x_tensor, torch.full_like(t_tensor, a_sc)], dim=0).unsqueeze(0)
    
    with torch.no_grad():
        pred = model(x_in).squeeze().numpy()
        
    # t=0 row must not be 0.0, but u0(x) = sin(pi * x)
    t0_pred = pred[0, :]
    t0_true = u_true[0, :]
    t0_mae = np.mean(np.abs(t0_pred - t0_true))
    
    assert t0_mae < 0.01, f"t=0 MAE on unmasked heat model is unexpectedly high: {t0_mae}"
    assert np.max(t0_pred) > 0.9, f"t=0 maximum should be ~1.0, got {np.max(t0_pred)}"

def test_poisson_fno_hard_mask_bc():
    """
    Test that Poisson FNO v2 model enforces homogeneous Dirichlet BC on all 4 borders.
    """
    ckpt_path = MODELS / "fno2d_poisson_v2.pt"
    assert os.path.exists(ckpt_path), f"Checkpoint missing: {ckpt_path}"
    
    ckpt = torch.load(ckpt_path, map_location="cpu")
    state_dict = ckpt if "model_state_dict" not in ckpt else ckpt["model_state_dict"]
    
    model = FNO2d(modes1=12, modes2=12, width=32, in_channels=3, out_channels=1, use_hard_mask=True)
    model.load_state_dict(state_dict)
    model.eval()
    
    x = torch.randn(2, 3, 64, 64)
    with torch.no_grad():
        out = model(x)
        
    assert torch.all(out[:, :, 0, :] == 0.0), "Poisson row 0 must be 0"
    assert torch.all(out[:, :, -1, :] == 0.0), "Poisson row -1 must be 0"
    assert torch.all(out[:, :, :, 0] == 0.0), "Poisson col 0 must be 0"
    assert torch.all(out[:, :, :, -1] == 0.0), "Poisson col -1 must be 0"

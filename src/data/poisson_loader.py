import os
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader

class PoissonGridDataset(Dataset):
    """
    PyTorch Dataset for 2D Poisson:
    Input: (f, x, y) tensor of shape (3, N, N)
    Output: u tensor of shape (1, N, N)
    """
    def __init__(self, data_path):
        data = np.load(data_path)
        self.F = data["F"] # (num_samples, N, N)
        self.U = data["U"] # (num_samples, N, N)
        self.seeds = data["seeds"]
        self.grid_x = data["grid_x"] # (N,)
        self.grid_y = data["grid_y"] # (N,)
        
        N = len(self.grid_x)
        X, Y = np.meshgrid(self.grid_x, self.grid_y, indexing='ij')
        
        # Build coordinate channels (2, N, N)
        coords = np.stack([X, Y], axis=0).astype(np.float32)
        self.coords = torch.from_numpy(coords) # (2, N, N)
        
        self.F_tensor = torch.from_numpy(self.F).unsqueeze(1) # (num_samples, 1, N, N)
        self.U_tensor = torch.from_numpy(self.U).unsqueeze(1) # (num_samples, 1, N, N)

    def __len__(self):
        return len(self.F)

    def __getitem__(self, idx):
        # Concatenate f with x, y coords -> (3, N, N)
        x_in = torch.cat([self.F_tensor[idx], self.coords], dim=0)
        y_out = self.U_tensor[idx]
        return x_in, y_out

def get_dataloader(data_path, batch_size=32, shuffle=True):
    dataset = PoissonGridDataset(data_path)
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle)

def load_all_splits(data_dir="data", version="v2"):
    prefix = f"poisson_{version}_" if version == "v2" else "poisson_"
    split_names = [
        "train", "val", "test_interp",
        "test_ood_narrow", "test_ood_count", "test_ood_boundary"
    ]
    if version == "v2":
        split_names.append("test_ood_highmodes")
        
    target_dir = data_dir
    if not os.path.exists(os.path.join(data_dir, f"{prefix}{split_names[0]}.npz")):
        arch_dir = os.path.join("archive", "superseded")
        if os.path.exists(os.path.join(arch_dir, f"{prefix}{split_names[0]}.npz")):
            target_dir = arch_dir

    splits = {}
    for name in split_names:
        p = os.path.join(target_dir, f"{prefix}{name}.npz")
        splits[name] = np.load(p)
    return splits

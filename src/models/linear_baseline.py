import os
import time
import numpy as np

class LinearPoissonBaseline:
    """
    Linear baseline for 2D Poisson: u = G f.
    Because -nabla^2 u = f is linear, the discrete solution operator u_int = A^{-1} f_int
    is an exact linear map. We fit this map via Ridge Regression on the training set:
        min_W ||F W - U||_F^2 + lambda ||W||_F^2
    Using the dual kernel formulation:
        W = F^T (F F^T + lambda I)^{-1} U
    Predictions:
        U_hat = (F_new F^T) ((F F^T + lambda I)^{-1} U)
    Boundary conditions u = 0 are strictly maintained.
    """
    def __init__(self, alpha_reg=1e-5):
        self.alpha_reg = alpha_reg
        self.F_train = None
        self.dual_coef = None # shape: (N_train, D_out)
        self.train_time = 0.0

    def fit(self, F_train, U_train, val_data=None):
        """
        F_train: (N_samples, H, W)
        U_train: (N_samples, H, W)
        """
        t0 = time.time()
        N, H, W = F_train.shape
        self.H = H
        self.W = W
        
        # Flatten spatial dimensions
        F_flat = F_train.reshape(N, -1).astype(np.float64) # (N, 4096)
        U_flat = U_train.reshape(N, -1).astype(np.float64) # (N, 4096)
        
        if val_data is not None:
            # Tune lambda over candidate grid using validation data
            F_val, U_val = val_data
            best_reg = self.alpha_reg
            best_val_err = float("inf")
            candidate_regs = [1e-8, 1e-6, 1e-5, 1e-4, 1e-3, 1e-2]
            
            # Compute Gram matrix K = F F^T once
            K = F_flat @ F_flat.T
            F_val_flat = F_val.reshape(len(F_val), -1).astype(np.float64)
            K_val = F_val_flat @ F_flat.T
            
            for reg in candidate_regs:
                try:
                    reg_mat = K + reg * np.eye(N)
                    alpha = np.linalg.solve(reg_mat, U_flat)
                    U_val_pred = K_val @ alpha
                    val_err = np.mean(
                        np.linalg.norm(U_val_pred - U_val.reshape(len(U_val), -1), axis=1) /
                        (np.linalg.norm(U_val.reshape(len(U_val), -1), axis=1) + 1e-12)
                    )
                    if val_err < best_val_err:
                        best_val_err = val_err
                        best_reg = reg
                except np.linalg.LinAlgError:
                    continue
            self.alpha_reg = best_reg
            
        # Final fit with optimal regularizer
        self.F_train = F_flat
        K = self.F_train @ self.F_train.T
        reg_mat = K + self.alpha_reg * np.eye(N)
        self.dual_coef = np.linalg.solve(reg_mat, U_flat)
        self.train_time = time.time() - t0
        return self

    def predict(self, F):
        """
        Predict solution u for source f.
        F: (M, H, W) or (H, W)
        Returns:
            U_pred: (M, H, W) with hard zero boundary enforced
        """
        is_single = (F.ndim == 2)
        if is_single:
            F = F[None, ...]
            
        M, H, W = F.shape
        F_flat = F.reshape(M, -1).astype(np.float64)
        
        # Kernel evaluation against training sources: (M, N) @ (N, D) -> (M, D)
        K_test = F_flat @ self.F_train.T
        U_pred_flat = K_test @ self.dual_coef
        
        U_pred = U_pred_flat.reshape(M, H, W).astype(np.float32)
        # Enforce zero boundary condition
        U_pred[:, 0, :] = 0.0
        U_pred[:, -1, :] = 0.0
        U_pred[:, :, 0] = 0.0
        U_pred[:, :, -1] = 0.0
        
        if is_single:
            return U_pred[0]
        return U_pred

    def save(self, filepath):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        np.savez_compressed(
            filepath,
            F_train=self.F_train.astype(np.float32),
            dual_coef=self.dual_coef.astype(np.float32),
            alpha_reg=self.alpha_reg,
            H=self.H,
            W=self.W,
            train_time=self.train_time
        )

    def load(self, filepath):
        data = np.load(filepath)
        self.F_train = data["F_train"].astype(np.float64)
        self.dual_coef = data["dual_coef"].astype(np.float64)
        self.alpha_reg = float(data["alpha_reg"])
        self.H = int(data["H"])
        self.W = int(data["W"])
        self.train_time = float(data["train_time"])
        return self

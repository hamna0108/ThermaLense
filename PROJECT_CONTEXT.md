# Project Context: Neural PDE Digital Twin

## Mission & Executive Scope
The goal of this project is the construction, rigorous verification, and benchmarking of a real-time Physics-Informed Digital Twin system governed by partial differential equations (PDEs). The system bridges classical numerical discretization methods (finite difference, direct sparse factorization) with modern data-driven and physics-informed deep learning operators (Fourier Neural Operators, Physics-Informed Neural Networks).

## Mathematical Formulation

### 1. 1D Transient Heat Equation (Stage 1)
Governed by:
$$\frac{\partial u}{\partial t} = \alpha \frac{\partial^2 u}{\partial x^2}, \quad x \in [0, 1], \; t \in [0, 1]$$
- **Boundary Conditions:** Dirichlet homogeneous boundary conditions $u(0, t) = u(1, t) = 0$.
- **Initial Condition:** $u(x, 0) = \sin(\pi x)$.
- **Analytical Solution:** $u_{\text{exact}}(x, t) = e^{-\alpha \pi^2 t} \sin(\pi x)$.
- **Parameter Domain:** Diffusivity $\alpha \in [0.01, 1.0]$ (interpolation) with OOD evaluations down to $\alpha = 0.005$ and up to $\alpha = 2.5$.
- **Inverse Objective:** Given sparse, noisy observations at $N$ sensors $y_i = u(x_i, t_i; \alpha) + \epsilon_i$ with $\epsilon_i \sim \mathcal{N}(0, \sigma^2)$, estimate $\hat{\alpha}$ accurately in real time and evaluate estimator spread against the Cramér-Rao lower bound.

### 2. 2D Steady-State Poisson Equation (Stage 2)
Governed by:
$$-\nabla^2 u(x, y) = -\left(\frac{\partial^2 u}{\partial x^2} + \frac{\partial^2 u}{\partial y^2}\right) = f(x, y), \quad (x, y) \in [0, 1]^2$$
- **Boundary Conditions:** Homogeneous Dirichlet $u|_{\partial\Omega} = 0$.
- **Source Distributions:** Gaussian radial mixtures $f(x, y) = \sum_{k=1}^K A_k \exp\left(-\frac{(x - x_k)^2 + (y - y_k)^2}{2\sigma_k^2}\right)$, high-frequency sinusoidal Fourier modes, and single manufactured benchmarks.wqes
- **Forward Operator Objective:** Learn mapping $\mathcal{G}_\theta: f \mapsto u$ using FNO-2D with zero-boundary enforcement, evaluated against classical direct sparse LU factorization and dual linear ridge regression.

## Core Capabilities
1. **Forward Surrogates:** Sub-millisecond FNO operators for transient heat and steady-state Poisson fields.
2. **Inverse Digital Twin Inversion:** Mode 2 (Classical Crank-Nicolson Spline), Mode 3 (FNO Spline autograd), and Mode 3+ (Solver Polish ablation).
3. **Sensor Placement (Task A):** Two-stage adaptive spatial-temporal sensor selection optimized against Fisher information and Cramér-Rao lower bound.
4. **Frozen PINN Inversion (Task B):** Gradient-based inversion through bounded reparametrized neural networks.
5. **Anomaly & Failure Detection:** Real-time physics-informed statistical rule detector discriminating between sensor hardware malfunctions and underlying physical model shifts.

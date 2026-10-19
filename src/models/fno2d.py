import torch
import torch.nn as nn
import torch.nn.functional as F

class SpectralConv2d(nn.Module):
    def __init__(self, in_channels, out_channels, modes1=12, modes2=12):
        super(SpectralConv2d, self).__init__()
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.modes1 = modes1 
        self.modes2 = modes2 

        self.scale = (1.0 / (in_channels * out_channels))
        # Initialise with complex Gaussian weights
        self.weights1 = nn.Parameter(
            self.scale * torch.view_as_complex(torch.randn(in_channels, out_channels, self.modes1, self.modes2, 2))
        )
        self.weights2 = nn.Parameter(
            self.scale * torch.view_as_complex(torch.randn(in_channels, out_channels, self.modes1, self.modes2, 2))
        )

    def compl_mul2d(self, input, weights):
        # (batch, in_channel, x, y), (in_channel, out_channel, x, y) -> (batch, out_channel, x, y)
        return torch.einsum("bixy,ioxy->boxy", input, weights)

    def forward(self, x):
        batchsize = x.shape[0]
        # x: (batch, channels, H, W)
        x_ft = torch.fft.rfft2(x)

        out_ft = torch.zeros(
            batchsize, self.out_channels, x.size(-2), x.size(-1)//2 + 1,
            dtype=torch.cfloat, device=x.device
        )
        out_ft[:, :, :self.modes1, :self.modes2] = \
            self.compl_mul2d(x_ft[:, :, :self.modes1, :self.modes2], self.weights1)
        out_ft[:, :, -self.modes1:, :self.modes2] = \
            self.compl_mul2d(x_ft[:, :, -self.modes1:, :self.modes2], self.weights2)

        x = torch.fft.irfft2(out_ft, s=(x.size(-2), x.size(-1)))
        return x

class FNO2d(nn.Module):
    """
    2D Fourier Neural Operator mapping (f, x, y) to u.
    Modes: 12x12, width: 32.
    Enforces Dirichlet zero boundary conditions via a hard boundary mask.
    """
    def __init__(self, modes1=12, modes2=12, width=32, in_channels=3, out_channels=1, use_hard_mask=False):
        super(FNO2d, self).__init__()

        self.modes1 = modes1
        self.modes2 = modes2
        self.width = width
        self.use_hard_mask = use_hard_mask
        
        self.fc0 = nn.Linear(in_channels, self.width)
        
        self.conv0 = SpectralConv2d(self.width, self.width, self.modes1, self.modes2)
        self.conv1 = SpectralConv2d(self.width, self.width, self.modes1, self.modes2)
        self.conv2 = SpectralConv2d(self.width, self.width, self.modes1, self.modes2)
        self.conv3 = SpectralConv2d(self.width, self.width, self.modes1, self.modes2)
        
        self.w0 = nn.Conv2d(self.width, self.width, 1)
        self.w1 = nn.Conv2d(self.width, self.width, 1)
        self.w2 = nn.Conv2d(self.width, self.width, 1)
        self.w3 = nn.Conv2d(self.width, self.width, 1)
        
        self.fc1 = nn.Linear(self.width, 128)
        self.fc2 = nn.Linear(128, out_channels)

    def forward(self, x):
        # x shape: (batch, in_channels, H, W)
        batch, _, H, W = x.shape
        
        # Project to high-dim feature space
        x = x.permute(0, 2, 3, 1) # (B, H, W, in_channels)
        x = self.fc0(x)
        x = x.permute(0, 3, 1, 2) # (B, width, H, W)
        
        # Fourier Layer 0
        x1 = self.conv0(x)
        x2 = self.w0(x)
        x = F.gelu(x1 + x2)

        # Fourier Layer 1
        x1 = self.conv1(x)
        x2 = self.w1(x)
        x = F.gelu(x1 + x2)

        # Fourier Layer 2
        x1 = self.conv2(x)
        x2 = self.w2(x)
        x = F.gelu(x1 + x2)

        # Fourier Layer 3
        x1 = self.conv3(x)
        x2 = self.w3(x)
        x = x1 + x2
        
        # Project back to output channels
        x = x.permute(0, 2, 3, 1) # (B, H, W, width)
        x = self.fc1(x)
        x = F.gelu(x)
        x = self.fc2(x) # (B, H, W, out_channels)
        x = x.permute(0, 3, 1, 2) # (B, out_channels, H, W)
        
        # Boundary masking
        if self.use_hard_mask is True or self.use_hard_mask in ('2d', 'poisson'):
            # Enforce zero Dirichlet on all 4 boundaries (Poisson 2D: x=0,1 and y=0,1)
            mask = torch.ones((1, 1, H, W), device=x.device, dtype=x.dtype)
            mask[:, :, 0, :] = 0.0
            mask[:, :, -1, :] = 0.0
            mask[:, :, :, 0] = 0.0
            mask[:, :, :, -1] = 0.0
            x = x * mask
        elif self.use_hard_mask in ('spatial_only', 'heat'):
            # Enforce zero Dirichlet only on spatial boundaries x=0,1 (Heat 1D: columns 0 and -1)
            # Row 0 (t=0, initial condition) and Row -1 (t=1, end state) remain unmasked.
            mask = torch.ones((1, 1, H, W), device=x.device, dtype=x.dtype)
            mask[:, :, :, 0] = 0.0
            mask[:, :, :, -1] = 0.0
            x = x * mask
            
        return x

def rel_l2_loss(pred, target):
    """
    Computes batch-averaged Relative L2 loss:
    loss = mean_b ||pred_b - target_b||_2 / ||target_b||_2
    """
    diff = pred.reshape(pred.size(0), -1) - target.reshape(target.size(0), -1)
    target_flat = target.reshape(target.size(0), -1)
    
    diff_norms = torch.norm(diff, p=2, dim=1)
    target_norms = torch.norm(target_flat, p=2, dim=1)
    return torch.mean(diff_norms / (target_norms + 1e-8))

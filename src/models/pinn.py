import torch
import torch.nn as nn

class PINN(nn.Module):
    def __init__(self, layers=[3, 64, 64, 64, 64, 1], activation=nn.Tanh()):
        super(PINN, self).__init__()
        self.layers = nn.ModuleList()
        for i in range(len(layers) - 1):
            self.layers.append(nn.Linear(layers[i], layers[i+1]))
        self.activation = activation

    def forward(self, x, t, alpha):
        # input is [batch_size, 3] containing (x, t, alpha_scaled)
        inputs = torch.cat([x, t, alpha], dim=-1)
        out = inputs
        for i in range(len(self.layers) - 1):
            out = self.activation(self.layers[i](out))
        out = self.layers[-1](out)
        return out

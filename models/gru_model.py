"""Direct GRU forecaster with fresh hidden state for each input window."""
import torch
from torch import nn


class TrafficGRU(nn.Module):
    def __init__(self, input_features=8, hidden_size=64, layers=2):
        super().__init__()
        self.recurrent = nn.GRU(input_features, hidden_size, num_layers=layers,
                                batch_first=True, dropout=0.0)
        self.output = nn.Linear(hidden_size, 1)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        sequence, _ = self.recurrent(inputs)
        return self.output(sequence[:, -1]).squeeze(-1)

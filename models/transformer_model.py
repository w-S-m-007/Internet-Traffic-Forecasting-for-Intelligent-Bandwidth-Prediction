"""Compact direct forecaster attending only to the supplied historical window."""

import math

import torch
from torch import nn
from torch.nn.attention import SDPBackend, sdpa_kernel


class TrafficTransformer(nn.Module):
    def __init__(self, input_features=8, model_dimension=64, layers=2,
                 attention_heads=4, feedforward_dimension=128, history_records=18):
        super().__init__()
        if model_dimension % 2 or model_dimension % attention_heads:
            raise ValueError("Model dimension must be even and divisible by attention heads")
        self.input_projection = nn.Linear(input_features, model_dimension)
        positions = torch.arange(history_records, dtype=torch.float32).unsqueeze(1)
        frequencies = torch.exp(torch.arange(0, model_dimension, 2, dtype=torch.float32)
                                * (-math.log(10000.) / model_dimension))
        encoding = torch.zeros(history_records, model_dimension)
        encoding[:, 0::2] = torch.sin(positions * frequencies)
        encoding[:, 1::2] = torch.cos(positions * frequencies)
        self.register_buffer("position_encoding", encoding.unsqueeze(0))
        # Construct layers separately so their initial attention weights differ.
        self.layers = nn.ModuleList([
            nn.TransformerEncoderLayer(d_model=model_dimension, nhead=attention_heads,
                                       dim_feedforward=feedforward_dimension, dropout=0.,
                                       activation="gelu", batch_first=True, norm_first=False)
            for _ in range(layers)
        ])
        self.output = nn.Linear(model_dimension, 1)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        if inputs.ndim != 3 or not 0 < inputs.shape[1] <= self.position_encoding.shape[1]:
            raise ValueError("Expected a batch with one to eighteen historical observations")
        hidden = self.input_projection(inputs) + self.position_encoding[:, :inputs.shape[1]]
        # All positions are known history. No forecast-target token is supplied.
        with sdpa_kernel(SDPBackend.MATH):
            for layer in self.layers:
                hidden = layer(hidden)
        return self.output(hidden[:, -1]).squeeze(-1)

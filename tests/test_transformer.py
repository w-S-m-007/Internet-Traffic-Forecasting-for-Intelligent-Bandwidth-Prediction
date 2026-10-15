"""Check independent windows, checkpointing, gradients and positional encoding."""

import unittest

import torch

from models.transformer_model import TrafficTransformer
from tests import test_lstm


class TransformerTests(test_lstm.LSTMTests):
    model_class = TrafficTransformer

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.previous_fastpath = torch.backends.mha.get_fastpath_enabled()
        torch.backends.mha.set_fastpath_enabled(False)

    @classmethod
    def tearDownClass(cls):
        torch.backends.mha.set_fastpath_enabled(cls.previous_fastpath)

    def test_positions_are_distinct_and_layers_initialize_independently(self):
        torch.manual_seed(42)
        model = self.model_class()
        self.assertFalse(torch.equal(model.position_encoding[:, 0], model.position_encoding[:, 1]))
        self.assertFalse(torch.equal(model.layers[0].self_attn.in_proj_weight,
                                     model.layers[1].self_attn.in_proj_weight))
        before = model.position_encoding.clone()
        model(torch.randn(2, 18, 8))
        torch.testing.assert_close(model.position_encoding, before)

    def test_oversized_history_is_rejected(self):
        with self.assertRaises(ValueError):
            self.model_class()(torch.randn(2, 19, 8))


if __name__ == "__main__":
    unittest.main()

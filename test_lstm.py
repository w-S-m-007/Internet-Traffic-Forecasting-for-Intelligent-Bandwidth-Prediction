"""Check independent windows and checkpoint inference before real training."""

import tempfile
import unittest
from pathlib import Path

import torch

from lstm_model import TrafficLSTM


class LSTMTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_optimizer_step_has_finite_gradients_and_changes_weights(self):
        torch.manual_seed(42)
        model = TrafficLSTM()
        inputs, targets = torch.randn(8, 18, 8), torch.randn(8)
        optimizer = torch.optim.Adam(model.parameters(), lr=.001)
        before = model.output.weight.detach().clone()
        loss = torch.nn.functional.mse_loss(model(inputs), targets)
        loss.backward()
        self.assertTrue(torch.isfinite(loss).item())
        self.assertTrue(all(parameter.grad is not None and torch.isfinite(parameter.grad).all().item()
                            for parameter in model.parameters()))
        optimizer.step()
        self.assertFalse(torch.equal(before, model.output.weight))

    def test_windows_do_not_share_hidden_state(self):
        torch.manual_seed(42)
        model = TrafficLSTM().eval()
        inputs = torch.randn(3, 18, 8)
        with torch.inference_mode():
            together = model(inputs)
            separate = torch.cat([model(window.unsqueeze(0)) for window in inputs])
        self.assertEqual(tuple(together.shape), (3,))
        torch.testing.assert_close(together, separate)

    def test_checkpoint_restores_predictions(self):
        torch.manual_seed(42)
        model = TrafficLSTM().eval()
        inputs = torch.randn(2, 18, 8)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "weights.pt"
            torch.save(model.state_dict(), path)
            restored = TrafficLSTM().eval()
            restored.load_state_dict(torch.load(path, weights_only=True))
            with torch.inference_mode():
                torch.testing.assert_close(model(inputs), restored(inputs))


if __name__ == "__main__":
    torch.set_num_threads(1)
    unittest.main()

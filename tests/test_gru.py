"""Check GRU gradients, independent windows and checkpoint restoration."""
import unittest
from models.gru_model import TrafficGRU
from tests import test_lstm


class GRUTests(test_lstm.LSTMTests):
    model_class = TrafficGRU


if __name__ == "__main__":
    unittest.main()

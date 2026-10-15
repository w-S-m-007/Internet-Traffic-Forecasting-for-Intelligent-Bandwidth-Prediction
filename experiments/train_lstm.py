"""LSTM command; training and prediction helpers are shared across neural models."""

from experiments.train_neural import main, plot_learning, predict, validation_mse


if __name__ == "__main__":
    main("lstm")

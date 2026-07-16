from types import SimpleNamespace

from robomimic.utils.train_cli_utils import apply_train_cli_overrides


class FakeConfig(SimpleNamespace):
    def unlock(self):
        self.unlock_called = True

    def lock_keys(self):
        self.lock_keys_called = True


def _config():
    return FakeConfig(
        unlock_called=False,
        lock_keys_called=False,
        experiment=SimpleNamespace(
            name="template",
            epoch_every_n_steps=100,
            validation_epoch_every_n_steps=10,
            rollout=SimpleNamespace(rate=50, n=50, horizon=400),
            save=SimpleNamespace(every_n_epochs=50),
        ),
        train=SimpleNamespace(
            data=None,
            num_epochs=2000,
            output_dir="../bc_trained_models",
        ),
    )


def test_debug_mode_is_short_and_persistent_output_wins():
    config = _config()
    args = SimpleNamespace(
        dataset="/data/lift.hdf5",
        name="lift-smoke",
        debug=True,
        output_dir="/opt/robomimic/outputs/training",
    )

    apply_train_cli_overrides(config, args)

    assert config.train.data == [{"path": "/data/lift.hdf5"}]
    assert config.experiment.name == "lift-smoke"
    assert config.train.num_epochs == 2
    assert config.experiment.epoch_every_n_steps == 3
    assert config.experiment.validation_epoch_every_n_steps == 3
    assert config.experiment.rollout.rate == 1
    assert config.experiment.rollout.n == 2
    assert config.experiment.rollout.horizon == 10
    assert config.experiment.save.every_n_epochs == 1
    assert config.train.output_dir == "/opt/robomimic/outputs/training"
    assert config.unlock_called and config.lock_keys_called


def test_full_training_preserves_template_defaults_without_overrides():
    config = _config()
    args = SimpleNamespace(
        dataset=None,
        name=None,
        debug=False,
        output_dir=None,
    )

    apply_train_cli_overrides(config, args)

    assert config.train.num_epochs == 2000
    assert config.experiment.save.every_n_epochs == 50
    assert config.train.output_dir == "../bc_trained_models"

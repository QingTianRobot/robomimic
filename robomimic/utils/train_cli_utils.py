import traceback


def apply_train_cli_overrides(config, args):
    if args.dataset is not None:
        config.train.data = [{"path": args.dataset}]

    if args.name is not None:
        config.experiment.name = args.name

    if args.debug:
        config.unlock()
        config.lock_keys()
        config.experiment.epoch_every_n_steps = 3
        config.experiment.validation_epoch_every_n_steps = 3
        config.train.num_epochs = 2
        config.experiment.rollout.rate = 1
        config.experiment.rollout.n = 2
        config.experiment.rollout.horizon = 10
        config.experiment.render_video = False
        config.experiment.save.every_n_epochs = 1
        config.train.output_dir = "/tmp/tmp_trained_models"

    if args.output_dir is not None:
        config.train.output_dir = args.output_dir


def run_training_with_status(train_fn, config, device, resume):
    try:
        train_fn(config, device=device, resume=resume)
    except Exception as exc:
        message = "run failed with error:\n{}\n\n{}".format(
            exc,
            traceback.format_exc(),
        )
        return 1, message
    return 0, "finished run successfully!"

"""Configuration loader for tournament settings."""

import os

import yaml

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")

REQUIRED_KEYS = {
    "critic_model": str,
    "author_model": str,
    "synthesizer_model": str,
    "judge_model": str,
    "num_judges": int,
    "max_passes": int,
    "convergence_threshold": int,
    "max_description_chars": int,
    "call_timeout": int,
}


def load_config(path: str | None = None) -> dict:
    """Load and validate tournament configuration from YAML.

    Args:
        path: Override path to config file. Defaults to config.yaml in this directory.

    Returns:
        Configuration dict with all tournament settings.

    Raises:
        ValueError: If required keys are missing or max_passes exceeds safety limit.
        TypeError: If config values have wrong types.
    """
    config_file = path or CONFIG_PATH
    with open(config_file) as f:
        config = yaml.safe_load(f)

    for key, typ in REQUIRED_KEYS.items():
        if key not in config:
            raise ValueError(f"Missing config key: {key}")
        if not isinstance(config[key], typ):
            raise TypeError(
                f"Config {key} must be {typ.__name__}, got {type(config[key]).__name__}"
            )

    if config["max_passes"] > 100:
        raise ValueError(f"max_passes {config['max_passes']} exceeds safety limit of 100")

    return config

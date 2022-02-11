from pathlib import Path

import yaml


def load_config():
    with open(Path(Path(__file__).parent, 'config.yaml'), 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


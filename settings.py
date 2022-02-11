from pathlib import Path

import yaml

BASE_DIR = Path(__file__).parent
log_path = Path(Path(BASE_DIR, 'logs'))

def load_config():
    with open(Path(Path(__file__).parent, 'config.yaml'), 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


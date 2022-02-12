import sys
from pathlib import Path

import yaml
from loguru import logger

from base.driver import Driver
from base.faceit import FaceIt


def load_config():
    with open("output/config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


config = load_config()
log_path = Path("logs")

logger.remove()

log_path.mkdir(exist_ok=True, parents=True)
logger.add(
    sink=sys.stderr,
    level=config.get("log_level"),
    enqueue=True,
    diagnose=True,
)
logger.add(
    sink=Path(log_path, "marklog.log"),
    level="TRACE",
    enqueue=True,
    encoding="utf-8",
    diagnose=True,
)


def main():
    driver = getattr(Driver, config["webdriver"])
    driver_path = driver.Manager().install()
    atr = FaceIt(config, driver, driver_path, log_path)
    logger.info("Настройки загружены")
    atr.start()


if __name__ == "__main__":
    main()

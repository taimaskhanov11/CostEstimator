import sys
from pathlib import Path

from loguru import logger

from base.driver import Driver
from base.faceit import FaceIt
from settings import load_config, log_path

config = load_config()

logger.remove()

log_path.mkdir(exist_ok=True, parents=True)
logger.add(sink=sys.stderr, level=config.get('log_level'), enqueue=True, diagnose=True, )
logger.add(sink=Path(log_path, 'marklog.log'), level='TRACE', enqueue=True, encoding='utf-8', diagnose=True, )


def main():
    driver = getattr(Driver, config['webdriver'])
    driver_path = driver.Manager().install()
    atr = FaceIt(config, driver, driver_path)
    logger.info('Настройки загружены')
    atr.start()


if __name__ == '__main__':
    main()

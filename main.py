from pathlib import Path
from base.driver import Driver
from settings import load_config

BASE_DIR = Path(__file__).parent




def main():
    config = load_config()
    driver = getattr(Driver, config['webdriver'])
    # driver_path = ChromeDriverManager().install()
    driver_path = driver.Manager().install()



if __name__ == '__main__':
    main()

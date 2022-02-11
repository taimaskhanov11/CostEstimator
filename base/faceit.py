import enum
import json
import sys
import time
from pathlib import Path
from pprint import pprint

from loguru import logger
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions

import requests
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By

from base.driver import Firefox, Chrome, Driver
from settings import load_config

BASE_DIR = Path(__file__).parent.parent

logger.remove()
log_path = Path(BASE_DIR, 'logs')
log_path.mkdir(exist_ok=True, parents=True)
logger.add(sink=sys.stderr, level='TRACE', enqueue=True, diagnose=True, )
logger.add(sink=Path(log_path, 'marklog.log'), level='TRACE', enqueue=True, encoding='utf-8', diagnose=True, )


class ElementsPath(enum.Enum):
    pass


class FaceItApi:

    def __init__(self, config):
        self.api_key = config['api_key']
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': 'Bearer ' + self.api_key,
            'Accept': 'application/json',
        })


class FaceItSelenium:
    """FaceItSelenium"""

    def __init__(
            self,
            config: dict,
            driver: Firefox | Chrome,
            driver_path: str,
    ):
        self.config = config

        service = driver.Service(driver_path, log_path=str(Path(log_path, 'geckodriver.log')))

        options: FirefoxOptions | ChromeOptions = driver.Options()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")

        if self.config['headless']:
            options.add_argument('--headless')

        self.br = driver.Webdriver(service=service, options=options)

        self.login: str = self.config.get('login')
        self.password: str = self.config.get('password')
        self.home_page: str = self.config.get('home_page')
        self.price_page: str = self.config.get('price_page')
        self.dashboard: str = self.config.get('dashboard')

        self.delay: int = config.get('delay')
        self.br.implicitly_wait(3)

        # self.br.set_window_size(900, 600)

    # def __getattr__(self, item):
    #     getattr(self.browser, item)()

    def get(self, url):
        self.br.get(url)

    def sleep(self, s=0):
        time.sleep(self.delay + s)

    def _load_cookies(self, cookies_path):
        with open(cookies_path, 'r') as f:
            cookies: list = json.load(f)

        for cookie in cookies:
            self.br.add_cookie(cookie)

    def _save_cookies(self, data, path):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f)

    def refresh_checkout(self):
        try:
            self.wait_for(By.XPATH, "//*[contains(text(), 'Обновить')]").click()
        except TimeoutException as e:
            logger.error(e)

    def authorisation(self):
        cookies_path = f'{self.login}.json'
        if Path(cookies_path).exists():
            self._load_cookies(cookies_path)
            logger.info('Данные аккаунта выгружены из cookies')
            self.br.refresh()
        else:
            logger.debug('Заполнение данных')
            self.br.find_elements(By.CSS_SELECTOR, '.sc-kwQtLu.iIJmKa')[3].click()
            self.sleep()
            self.wait_for(By.ID, 'onetrust-accept-btn-handler').click()
            self.sleep()
            self.wait_for(By.NAME, 'email').send_keys(self.login)
            self.wait_for(By.NAME, 'password').send_keys(self.password)
            self.wait_for(By.CSS_SELECTOR, '.sc-haosql.jCRtnZ').click()
            self.sleep()

            logger.warning('Ожидание ввода капчи')
            self.sleep(30)

            # self.sleep(300)
            self._save_cookies(self.br.get_cookies(), cookies_path)
            logger.info('Куки сохранены')

    def wait_for(self, element_type, value, sec=2):
        res = WebDriverWait(self.br, sec).until(
            expected_conditions.presence_of_element_located(
                (element_type,
                 value)
            )
        )
        return res

    def work(self):
        self.get(self.dashboard)
        self.wait_for(By.XPATH, "//*[contains(text(), '5v5 RANKED')]").click()
        self.sleep(1)
        self.get(f'{self.br.current_url}/matches?state=ongoing')
        self.sleep(5)

        # matches = self.br.find_elements(By.CLASS_NAME, 'mb-md')
        # matches = self.br.find_elements(By.ID, 'match.id')
        matches = self.br.find_elements(By.CSS_SELECTOR, '.sc-beTgVM.cFRxyg')

        for match in matches:
            match.click()
            time.sleep(3)
        self.sleep(300)




    def start(self):
        logger.info('Запуск скрипта')
        try:
            logger.debug('Переход на главную страницу')
            self.br.get(self.home_page)
            logger.debug('Аутентификация...')
            self.authorisation()
            logger.info('Пользователь аутентифицирован')

            logger.debug('Начало основной логики')
            self.work()
            logger.info('Основная логика завершена')
        finally:
            logger.debug('Закрытые скрипта')
            self.br.close()
            self.br.quit()
            logger.info('Скрипт успешно закрыт')


if __name__ == '__main__':
    # driver_path = GeckoDriverManager().install()
    config = load_config()
    pprint(config)
    driver = Driver.Chrome
    atr = FaceItSelenium(config, driver, driver.Manager().install())
    atr.start()

import enum
import json
import random
import re
import sys
import time
from pathlib import Path
from pprint import pprint
from threading import Thread

from loguru import logger
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions

import requests
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By

from base.driver import Firefox, Chrome, Driver
from settings import load_config, log_path

BASE_DIR = Path(__file__).parent.parent


# class Elements(enum.Enum):
class Elements:
    RANKED_XPATH = "//*[contains(text(), '5v5 {}')]"

    # RANKED_CSS = ".flex-grow.m2l-sm.max-w-150.text-truncate"
    # RANKED_CSS = ".navigation-v2__line.clickable.show-hide-on-hover.flex-center-start.-active"
    # RANKED_XPATH = "//*[contains(@href, 'https://www.faceit.com/ru/matchmaking')]"

    MATCHES_CSS = '.sc-hvEELy.eDNMaf'
    # PLAYER_NICKNAME_XPATH = "//*[contains(text(), '{}')]"
    # PLAYER_NICKNAME_XPATH = "//div[text()='{}']"
    PLAYER_NICKNAME_XPATH = "//div[contains(text(),'{}')]"


class FaceItApi:

    def __init__(self, config):
        self.api_key = config.get('api_key')
        self.api_url = config.get('api_url')

        self.acc_api_key = config.get('acc_api_key')
        # self.acc_pre_token = config.get('acc_pre_token')
        self.acc_pre_token = None
        self.acc_api_player_url = config.get('acc_api_player_url')

        self.app_session = requests.Session()
        self.app_session.headers.update({
            'Authorization': 'Bearer ' + self.api_key,
            'Accept': 'application/json',
        })

        self.acc_session = requests.Session()  # todo 11.02.2022 20:27 taima:
        self.acc_session.headers.update({
            'content-type': 'application/json',
            'authorization': 'Bearer ' + self.acc_api_key,
        })

    def send_friendship_request(self, player_id):
        payload = {"users": [player_id], "conversionPoint": "profile"}
        url = f'https://api.faceit.com/friend-requests/v1/users/{self.acc_pre_token}/requests'
        payload = json.dumps(payload)
        res = self.acc_session.post(url, data=payload, )
        return res.json()

    def get_match(self, match_id: str) -> dict:
        res = self.app_session.get(f'{self.api_url}{match_id}')
        return res.json()

    def get_player_info(self, nickname):
        res = self.app_session.get(f'{self.acc_api_player_url}{nickname}')
        return res.json()


class LolzApi:
    """LolzApi:"""

    def __init__(self, config):
        self.cost_session = requests.Session()
        self.cost_session.headers.update(config['cost_session_headers'])
        self.params = config['cost_session_params']
        self.url = config['cost_session_url']

    def get_account_cost(self, steam_id):
        try:
            res = self.cost_session.post(
                self.url,
                params=self.params | {"link": steam_id},
                timeout=5
            )

            return res.json().get('totalValueSimple')
        except requests.exceptions.Timeout as e:
            logger.error(e)

        except Exception as e:
            logger.error(e)
            time.sleep(random.randint(0, 8))
            res = self.cost_session.post(
                self.url,
                params=self.params | {"link": steam_id},
                timeout=5
            )
            return res.json().get('totalValueSimple')


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
        self.br.maximize_window()
        # self.br.set_window_size(900, 600)

        self.login: str = self.config['login']
        self.password: str = self.config['password']
        self.home_page: str = self.config['home_page']
        self.price_page: str = self.config['price_page']
        self.dashboard: str = self.config['dashboard']
        self.player_url: str = self.config['player_url']

        self.match_type: str = self.config['match_type']
        self.players_level: int = config['player_level']
        self.player_account_cost: int = config['player_account_cost']

        self.delay: int = config['delay']
        self.wait_for_delay: int = config['wait_for']
        self.home_delay: int = config['home_delay']
        self.captcha_time:int  = config['captcha_time']
        self.br.implicitly_wait(3)

        self.home_tab = None
        self.cost_tab = None

        self.players_for_add = []
        self.steam_ids = []

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

    def get_tabs(self):
        self.br.execute_script(f'''window.open("{self.price_page}","_blank");''')
        self.home_tab = self.br.window_handles[0]
        self.cost_tab = self.br.window_handles[1]

    def switch_to(self, tab):
        self.br.switch_to.window(tab)

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
            self.sleep(self.captcha_time)

            # self.sleep(300)
            self._save_cookies(self.br.get_cookies(), cookies_path)
            logger.info('Куки сохранены')

    def wait_for(self, element_type, value, sec=None):
        sec = sec or self.wait_for_delay
        res = WebDriverWait(self.br, sec).until(
            expected_conditions.presence_of_element_located(
                (element_type,
                 value)
            )
        )
        return res


class FaceIt(FaceItApi, LolzApi, FaceItSelenium):
    """FaceIt(FaceItApi, FaceItSelenium)"""

    def __init__(
            self,
            config: dict,
            driver: Firefox | Chrome,
            driver_path: str,
    ):
        super().__init__(config)
        LolzApi.__init__(self, config)
        FaceItSelenium.__init__(self, config, driver, driver_path)

        # super
        # super(self, FaceItSelenium).__init__(config, driver, driver_path)

    def get_acc_pre_token(self):
        nickname = self.wait_for(By.CLASS_NAME, 'nickname')
        player = self.get_player_info(nickname.text)
        logger.trace(player)
        self.acc_pre_token = player['player_id']

        # self.acc_pre_token =

    def start(self):
        logger.info('Запуск скрипта')
        try:
            logger.debug('Переход на главную страницу')
            self.br.get(self.home_page)
            logger.debug('Открытие страницы для расчета цен')

            logger.debug('Аутентификация...')
            self.authorisation()
            logger.info('Пользователь аутентифицирован')

            logger.debug('Получение pre токена')
            self.get_acc_pre_token()
            logger.info('Pre токен успешно получен')

            logger.debug('Начало основной логики')
            self.work()
            logger.info('Основная логика завершена')

        except Exception as e:
            logger.error(e)
            raise e

        finally:
            logger.debug('Запись в файл')
            self.write_in_file()
            logger.info('Запись успешно завершена')

            logger.debug('Закрытые скрипта')
            # time.sleep(300)
            self.br.close()
            self.br.quit()
            logger.info('Скрипт успешно закрыт')

    def check_player(self, match_url):
        match_id = re.findall('room/(.*)', match_url)[0]
        logger.debug(f'Получение данных матча {match_id}')
        match = self.get_match(match_id)
        for player in [*match['teams']['faction1']['roster'], *match['teams']['faction2']['roster']]:
            logger.trace(player)
            if player['game_skill_level'] > self.players_level:
                logger.debug(f'{player["nickname"]} уровень больше {self.players_level}')
                continue
            logger.debug(f'Проверка стоимости аккаунта {player["nickname"]}')

            # time.sleep(1)
            acc_cost = self.get_account_cost(player['game_player_id'])

            if acc_cost:
                if acc_cost < self.player_account_cost:
                    logger.debug(f'{player["nickname"]} [{acc_cost}] стоимость меньше {self.player_account_cost}')
                    continue
                logger.success(f'{player["nickname"]} соответствует требованию')

                res = self.send_friendship_request(player['player_id'])
                logger.info(res)
                logger.success(f'Запрос в друзья {player["nickname"]} успешно отправлен')

                self.steam_ids.append(f"[{player['nickname']:20}] - {player['game_player_id']}")

                # self.players_for_add.append(player["nickname"])
                # self.players_for_add.append(match_url)
                # return
                # self.br.execute_script(f'''window.open("{self.player_url}{player["nickname"]}","_blank");''')
                # self.sleep(3)
                # print(self.wait_for(By.CSS_SELECTOR, '.sc-clsHhM.gYYSzb.sc-fbkhIv.cupfpU.sc-jyCHzk.jcwygp'))
                # exit()

    def write_in_file(self, ):
        with open('users_data.txt', 'a', encoding='utf-8') as f:
            f.write('\n'.join(self.steam_ids))

    def work(self):
        self.get(self.dashboard)
        self.sleep(self.home_delay)

        self.wait_for(By.XPATH, Elements.RANKED_XPATH.format(self.match_type)).click()

        self.sleep(self.home_delay)
        self.get(f'{self.br.current_url}/matches?state=ongoing')

        self.sleep(self.home_delay)

        matches = self.br.find_elements(By.CSS_SELECTOR, Elements.MATCHES_CSS)
        matches_urls = []
        logger.debug('Добавление матчей для проверки')
        for match in matches:
            match_url = match.get_attribute('href')
            logger.trace(match_url)
            matches_urls.append(match_url)

        logger.info('Матчи для проверки успешно добавлены')

        logger.debug('Получение данных игроков')

        match_threads = []
        for match_url in matches_urls:
            logger.debug(f'Проверка {match_url}')
            # self.get(match_url)
            # self.sleep(10)
            # print(self.wait_for(By.NAME, 'roster1'))
            # self.add_friend(match_url)

            # todo 11.02.2022 20:04 taima:
            # self.add_friend(match_url)

            # self.check_player(match_url)
            #
            match_threads.append(Thread(target=self.check_player, args=(match_url,)))  # todo 11.02.2022 20:40 taima:

            # logger.info(f'{match_url} добавлен в поток')

        logger.debug('Запуск потоков')
        [t.start() for t in match_threads]

        logger.debug('Ожидание завершения потоков')
        [t.join() for t in match_threads]
        logger.info('Потоки завершены')


        # logger.debug('Создание вкладок')
        # for player in self.players_for_add:
        #     self.br.execute_script(f'''window.open("{self.player_url}{player}","_blank");''')
        #     logger.info(f'Вкладка {player} создана')
        #
        # logger.debug('Переключение в вкладок')
        # for tab in self.br.window_handles[1:]:
        #     self.switch_to(tab)
        #     self.wait_for(By.CSS_SELECTOR, '.sc-clsHhM.gYYSzb.sc-fbkhIv.cupfpU.sc-jyCHzk.jcwygp', 5).click()
        #     logger.success("Запрос успешно отправлен")
        #
        # self.sleep(300)


if __name__ == '__main__':
    # driver_path = GeckoDriverManager().install()
    config = load_config()
    pprint(config)
    driver = Driver.Chrome
    atr = FaceIt(config, driver, driver.Manager().install())
    atr.start()

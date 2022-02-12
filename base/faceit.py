import json
import re
import time
from pathlib import Path
from threading import Thread

import requests
from loguru import logger
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

from base.driver import Firefox, Chrome

BASE_DIR = Path(__file__).parent.parent


class Elements:
    RANKED_XPATH = "//*[contains(text(), '5v5 {}')]"
    MATCHES_CSS = ".sc-hvEELy.eDNMaf"
    PLAYER_NICKNAME_XPATH = "//div[contains(text(),'{}')]"


class FaceItApi:
    def __init__(self, config):
        self.api_key = config.get("api_key")
        self.api_url = config.get("api_url")

        self.acc_api_key = config.get("acc_api_key")
        self.acc_pre_token = None
        self.acc_api_player_url = config.get("acc_api_player_url")

        self.app_session = requests.Session()
        self.app_session.headers.update(
            {
                "Authorization": "Bearer " + self.api_key,
                "Accept": "application/json",
            }
        )

        self.acc_session = requests.Session()  # todo 11.02.2022 20:27 taima:
        self.acc_session.headers.update(
            {
                "content-type": "application/json",
                "authorization": "Bearer " + self.acc_api_key,
            }
        )

    def send_friendship_request(self, player_id):
        payload = {"users": [player_id], "conversionPoint": "profile"}
        url = f"https://api.faceit.com/friend-requests/v1/users/{self.acc_pre_token}/requests"
        payload = json.dumps(payload)
        res = self.acc_session.post(
            url,
            data=payload,
        )
        return res.json()

    def get_match(self, match_id: str) -> dict:
        res = self.app_session.get(f"{self.api_url}{match_id}")
        return res.json()

    def get_player_info(self, nickname):
        res = self.app_session.get(f"{self.acc_api_player_url}{nickname}")
        return res.json()


class LolzApi:
    """LolzApi:"""

    def __init__(self, config):
        self.cost_session = requests.Session()
        self.cost_session_url = config["cost_session_url"]
        self.cost_session.headers.update(config["cost_session_headers"])
        self.cost_session_params = config["cost_session_params"]

    def get_account_cost(self, steam_id):
        # todo 12.02.2022 14:32 taima: пока не воркает
        try:
            res = self.cost_session.post(
                self.cost_session_url,
                params=self.cost_session_params | {"link": steam_id},
                timeout=5,
            )
            logger.info(res.text)
            return res.json().get("totalValueSimple")
        except requests.exceptions.Timeout as e:
            logger.error(e)

        except Exception as e:
            logger.error(e)

    def _check_error(self, br):
        try:
            br.find_element(By.CLASS_NAME, "heading")
            logger.debug(f"error Falce")
            return True
        except Exception as e:
            logger.debug(f"error True")
            return False


class FaceItSelenium:
    """FaceItSelenium"""

    def __init__(
        self,
        config: dict,
        driver: Firefox | Chrome,
        driver_path: str,
        log_path: Path,
    ):
        self.config = config
        self.driver = driver
        self.driver_path = driver_path
        self.log_path = log_path

        service = self.driver.Service(
            self.driver_path, log_path=str(Path(log_path, "geckodriver.log"))
        )

        options: FirefoxOptions | ChromeOptions = self.driver.Options()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")

        if self.config["headless"]:
            options.add_argument("--headless")

        self.br = self.driver.Webdriver(service=service, options=options)
        self.br.maximize_window()
        # self.br.set_window_size(900, 600)

        self.login: str = self.config["login"]
        self.password: str = self.config["password"]
        self.home_page: str = self.config["home_page"]
        self.price_page: str = self.config["price_page"]
        self.dashboard: str = self.config["dashboard"]
        self.player_url: str = self.config["player_url"]

        self.match_type: str = self.config["match_type"]
        self.players_level: int = config["player_level"]
        self.player_account_cost: int = config["player_account_cost"]

        self.delay: int = config["delay"]
        self.wait_for_delay: int = config["wait_for"]
        self.home_delay: int = config["home_delay"]
        self.captcha_time: int = config["captcha_time"]
        self.thread_count: int = config["thread_count"]

        self.br.implicitly_wait(3)

        self.home_tab = None
        self.cost_tab = None

        self.players_for_add = []
        self.steam_ids = []
        self.del_count = 0

    def get(self, url):
        self.br.get(url)

    def sleep(self, s=0):
        time.sleep(self.delay + s)

    def _load_cookies(self, cookies_path):
        with open(cookies_path, "r") as f:
            cookies: list = json.load(f)

        for cookie in cookies:
            self.br.add_cookie(cookie)

    def _save_cookies(self, data, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def refresh_checkout(self):
        try:
            self.wait_for(By.XPATH, "//*[contains(text(), 'Обновить')]").click()
        except TimeoutException as e:
            logger.error(e)

    def get_tabs(self):
        self.br.execute_script(f"""window.open("{self.price_page}","_blank");""")
        self.home_tab = self.br.window_handles[0]
        self.cost_tab = self.br.window_handles[1]

    def switch_to(self, tab):
        self.br.switch_to.window(tab)

    def authorisation(self):
        cookies_path = f"{self.login}.json"
        if Path(cookies_path).exists():
            self._load_cookies(cookies_path)
            logger.info("Данные аккаунта выгружены из cookies")
            self.br.refresh()
        else:
            logger.debug("Заполнение данных")
            self.br.find_elements(By.CSS_SELECTOR, ".sc-kwQtLu.iIJmKa")[3].click()
            self.sleep()
            self.wait_for(By.ID, "onetrust-accept-btn-handler").click()
            self.sleep()
            self.wait_for(By.NAME, "email").send_keys(self.login)
            self.wait_for(By.NAME, "password").send_keys(self.password)
            self.wait_for(By.CSS_SELECTOR, ".sc-haosql.jCRtnZ").click()
            self.sleep()

            logger.warning("Ожидание ввода капчи")
            self.sleep(self.captcha_time)
            self._save_cookies(self.br.get_cookies(), cookies_path)
            logger.info("Куки сохранены")

    def wait_for(self, element_type, value, sec=None, br=None):
        sec = sec or self.wait_for_delay
        br = br or self.br

        res = WebDriverWait(br, sec).until(
            expected_conditions.presence_of_element_located((element_type, value))
        )
        return res


class FaceIt(FaceItApi, LolzApi, FaceItSelenium):
    """FaceIt(FaceItApi, FaceItSelenium)"""

    def __init__(
        self,
        config: dict,
        driver: Firefox | Chrome,
        driver_path: str,
        log_path: Path,
    ):
        super().__init__(config)
        LolzApi.__init__(self, config)
        FaceItSelenium.__init__(self, config, driver, driver_path, log_path)

    def get_acc_cost(self, steam_id, br):
        but = self.wait_for(By.NAME, "link", 5, br)
        but.clear()
        but.send_keys(steam_id)
        self.wait_for(
            By.CSS_SELECTOR, ".submitButton.SubmitButton.button.primary.large", 5, br
        ).click()
        self.sleep(2)

        try_count = 0
        try:
            res = self.wait_for(By.CSS_SELECTOR, ".Value.mainc", 5, br)
            while not res.text:
                logger.warning(f"Повторная проверка [{steam_id}] {res.text} ")
                if try_count > 2:
                    break
                time.sleep(1)
                if self._check_error(br):
                    br.refresh()
                    self.sleep(2)
                    but = self.wait_for(By.NAME, "link", 5, br)
                    but.clear()
                    but.send_keys(steam_id)
                    self.wait_for(
                        By.CSS_SELECTOR,
                        ".submitButton.SubmitButton.button.primary.large",
                        5,
                        br,
                    ).click()
                try_count += 1
                res = self.wait_for(By.CSS_SELECTOR, ".Value.mainc", 5, br)
                logger.trace(res)

            res_text = res.text.strip().replace(" ", "")
            logger.trace(res_text)
            rub = re.findall(r"(.*)\.", res_text)
            logger.debug(res)
            return int(rub[0])

        except Exception as e:
            br.refresh()
            self.sleep(2)
            logger.error(e)

    def get_acc_pre_token(self):
        nickname = self.wait_for(By.CLASS_NAME, "nickname")
        player = self.get_player_info(nickname.text)
        logger.trace(player)
        self.acc_pre_token = player["player_id"]

    def start(self):
        logger.info("Запуск скрипта")
        try:
            logger.debug("Переход на главную страницу")
            self.br.get(self.home_page)
            logger.debug("Открытие страницы для расчета цен")

            logger.debug("Аутентификация...")
            self.authorisation()
            logger.info("Пользователь аутентифицирован")

            logger.debug("Получение pre токена")
            self.get_acc_pre_token()
            logger.info("Pre токен успешно получен")

            logger.debug("Начало основной логики")
            self.work()
            logger.info("Основная логика завершена")

        except Exception as e:
            logger.error(e)
            raise e

        finally:
            logger.debug("Запись в файл")
            self.write_in_file()
            logger.info("Запись успешно завершена")

            logger.debug("Закрытые скрипта")
            # time.sleep(300)
            self.br.close()
            self.br.quit()
            logger.info("Скрипт успешно закрыт")

    def check_player(self, match_url, br):
        logger.debug(f"Проверка {match_url}")
        br.get(self.cost_session_url)  # todo 12.02.2022 0:52 taima:
        self.sleep(5)

        match_id = re.findall("room/(.*)", match_url)[0]
        logger.debug(f"Получение данных матча {match_id}")
        match = self.get_match(match_id)
        for player in [
            *match["teams"]["faction1"]["roster"],
            *match["teams"]["faction2"]["roster"],
        ]:
            logger.trace(player)
            if player["game_skill_level"] > self.players_level:
                logger.debug(
                    f'{player["nickname"]} уровень больше {self.players_level}'
                )
                continue
            logger.debug(f'Проверка стоимости аккаунта {player["nickname"]}')

            # acc_cost = self.get_account_cost(player['game_player_id']) ##todo 12.02.2022 0:49 taima:
            acc_cost = self.get_acc_cost(player["game_player_id"], br)
            logger.info(acc_cost)
            if acc_cost:
                if acc_cost < self.player_account_cost:
                    logger.debug(
                        f'{player["nickname"]} [{acc_cost}] стоимость меньше {self.player_account_cost}'
                    )
                    continue

                logger.success(
                    f'{player["nickname"]} [{acc_cost}] соответствует требованию'
                )
                res = self.send_friendship_request(player["player_id"])
                logger.info(res)
                logger.success(
                    f'Запрос в друзья {player["nickname"]} успешно отправлен'
                )
                self.steam_ids.append(
                    f"[{player['nickname']:20}] - [{acc_cost:15} rub] - {player['game_player_id']}"
                )
                self.del_count += 1

                if self.del_count > 5:
                    logger.debug(f"Аккаунтов {self.del_count} больше 5. Запись в файл")
                    self.write_in_file()
                    self.steam_ids = []

    def write_in_file(
        self,
    ):
        with open("users_data.txt", "a", encoding="utf-8") as f:
            if self.steam_ids[-1]:
                self.steam_ids[-1] += "\n"
            f.write("\n".join(self.steam_ids))
            # f.write('\n')

    def _get_browser(self):
        service = self.driver.Service(
            self.driver_path, log_path=str(Path(self.log_path, "geckodriver.log"))
        )
        options: FirefoxOptions | ChromeOptions = self.driver.Options()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        br = self.driver.Webdriver(service=service, options=options)
        return br

    def work(self):
        self.get(self.dashboard)
        self.sleep(self.home_delay)

        self.wait_for(By.XPATH, Elements.RANKED_XPATH.format(self.match_type)).click()

        self.sleep(self.home_delay)
        self.get(f"{self.br.current_url}/matches?state=ongoing")

        self.sleep(self.home_delay)

        matches = self.br.find_elements(By.CSS_SELECTOR, Elements.MATCHES_CSS)
        matches_urls = []
        logger.debug("Добавление матчей для проверки")
        for match in matches:
            match_url = match.get_attribute("href")
            logger.trace(match_url)
            matches_urls.append(match_url)

        logger.info("Матчи для проверки успешно добавлены")

        logger.debug("Получение данных игроков")

        match_threads = []

        for match_url in matches_urls:
            thread = Thread(
                target=self.check_player, args=(match_url, self._get_browser())
            )
            match_threads.append(thread)

            if len(match_threads) >= self.thread_count:
                [mt.start() for mt in match_threads]
                [mt.join() for mt in match_threads]
                match_threads = []

            # if self.del_count > 5:
            #     logger.debug(f'Аккаунтов {self.del_count} больше 5. Запись в файл')
            #     self.write_in_file()
            #     self.steam_ids = []

        #     self.check_player(match_url, self.br)


if __name__ == "__main__":
    pass
    # driver_path = GeckoDriverManager().install()
    # config = load_config()
    # pprint(config)
    # driver = Driver.Chrome
    # atr = FaceIt(config, driver, driver.Manager().install())
    # atr.start()

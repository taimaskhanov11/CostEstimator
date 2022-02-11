from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium import webdriver

from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager


class Firefox:
    Service = FirefoxService
    Options = FirefoxOptions
    Manager = GeckoDriverManager
    Webdriver = webdriver.Firefox


class Chrome:
    Service = ChromeService
    Options = ChromeOptions
    Manager = ChromeDriverManager
    Webdriver = webdriver.Chrome


class Driver:
    Chrome = Chrome
    Firefox = Firefox

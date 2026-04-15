import os
from datetime import datetime
from pathlib import Path
import re
import shutil
import subprocess
from typing import List, Optional, Tuple

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

Locator = Tuple[By, str]


BASE_URL = "https://shopeefood.vn/"


def log_step(message: str) -> None:
    """In log tung buoc de de theo doi khi chay test."""
    time_text = datetime.now().strftime("%H:%M:%S")
    print(f"[{time_text}] {message}")


def setup_driver() -> webdriver.Chrome:
    """Khoi tao Chrome WebDriver bang webdriver-manager."""
    chrome_options = Options()
    chrome_options.binary_location = detect_chromium_binary()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    local_driver = (os.environ.get("CHROMEDRIVER_PATH") or "").strip()
    if local_driver and Path(local_driver).exists():
        service = Service(local_driver)
    else:
        browser_major = detect_browser_major_version(chrome_options.binary_location)
        if browser_major:
            service = Service(ChromeDriverManager(driver_version=browser_major).install())
        else:
            service = Service(ChromeDriverManager().install())

    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.implicitly_wait(1)
    return driver


def detect_chromium_binary() -> str:
    """Tu tim Chrome/Coc Coc binary tren may, uu tien bien moi truong."""
    env_value = (os.environ.get("CHROME_BINARY") or "").strip()
    if env_value and Path(env_value).exists():
        return env_value

    candidates = [
        Path(r"C:\Users\Admin\AppData\Local\CocCoc\Browser\Application\browser.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files\CocCoc\Browser\Application\browser.exe"),
        Path(r"C:\Program Files (x86)\CocCoc\Browser\Application\browser.exe"),
    ]
    for path in candidates:
        if path.exists():
            return str(path)

    for exe_name in ["chrome.exe", "chrome", "browser.exe"]:
        found = shutil.which(exe_name)
        if found:
            return found

    raise FileNotFoundError(
        "Khong tim thay Chrome/Coc Coc binary. "
        "Hay cai trinh duyet hoac set bien CHROME_BINARY tro den file .exe"
    )


def detect_browser_major_version(binary_path: str) -> Optional[str]:
    """Lay major version trinh duyet (vi du 145) de chon chromedriver dung."""
    try:
        output = subprocess.check_output([binary_path, "--version"], text=True, stderr=subprocess.STDOUT, timeout=5)
        match = re.search(r"(\d+)\.", output)
        if match:
            return match.group(1)
    except Exception:
        pass

    try:
        escaped = binary_path.replace("'", "''")
        ps_cmd = f"(Get-Item '{escaped}').VersionInfo.FileVersion"
        output = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            text=True,
            stderr=subprocess.STDOUT,
            timeout=8,
        ).strip()
        match = re.search(r"(\d+)\.", output)
        if match:
            return match.group(1)
    except Exception:
        return None

    return None


def safe_quit(driver: Optional[webdriver.Chrome]) -> None:
    if driver:
        driver.quit()


def take_screenshot(driver: webdriver.Chrome, name_prefix: str) -> str:
    """Chup screenshot khi co loi de de debug."""
    os.makedirs("screenshots", exist_ok=True)
    file_name = f"{name_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    path = os.path.join("screenshots", file_name)
    driver.save_screenshot(path)
    log_step(f"Da chup screenshot: {path}")
    return path


def open_homepage(driver: webdriver.Chrome, url: str = BASE_URL) -> None:
    log_step("Mo website ShopeeFood")
    driver.get(url)


def find_first_element(
    driver: webdriver.Chrome,
    locators: List[Locator],
    timeout: int = 12,
    clickable: bool = False,
) -> WebElement:
    """Tim phan tu theo danh sach locator de tang do ben khi UI thay doi."""
    last_error = None
    wait = WebDriverWait(driver, timeout)

    for locator in locators:
        try:
            if clickable:
                return wait.until(EC.element_to_be_clickable(locator))
            return wait.until(EC.presence_of_element_located(locator))
        except Exception as ex:
            last_error = ex

    raise TimeoutException(f"Khong tim duoc element voi danh sach locator. Loi cuoi: {last_error}")


def safe_click(driver: webdriver.Chrome, element: WebElement) -> None:
    """Tu xu ly scroll + click JavaScript neu click thuong bi chan."""
    try:
        element.click()
    except Exception:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
        driver.execute_script("arguments[0].click();", element)


def close_popup_if_any(driver: webdriver.Chrome) -> None:
    """Dong popup quang cao neu xuat hien."""
    log_step("Kiem tra popup neu co")

    popup_close_locators: List[Locator] = [
        (By.XPATH, "//button[contains(.,'Dong') or contains(.,'Đóng') or contains(.,'x') or contains(.,'X') ]"),
        (By.XPATH, "//span[contains(.,'Đóng') or contains(.,'Dong')]/ancestor::button"),
        (By.XPATH, "//div[contains(@class,'modal') or contains(@class,'popup')]//button"),
        (By.CSS_SELECTOR, ".modal button, .popup button, .shopee-popup__close-btn"),
    ]

    for locator in popup_close_locators:
        try:
            elements = driver.find_elements(*locator)
            for element in elements:
                if element.is_displayed() and element.is_enabled():
                    safe_click(driver, element)
                    log_step("Da dong popup")
                    return
        except Exception:
            continue


def search_food(driver: webdriver.Chrome, keyword: str) -> None:
    """Tim mon an voi tu khoa."""
    log_step(f"Tim mon an voi tu khoa: {keyword}")

    search_input = find_first_element(
        driver,
        [
            (By.CSS_SELECTOR, "input[placeholder*='Tìm']"),
            (By.CSS_SELECTOR, "input[placeholder*='tim']"),
            (By.CSS_SELECTOR, "input[type='search']"),
            (By.XPATH, "//input[contains(@placeholder,'Tìm') or contains(@placeholder,'tim')]")
        ],
        timeout=20,
        clickable=True,
    )

    search_input.clear()
    search_input.send_keys(keyword)
    search_input.send_keys(Keys.ENTER)


def wait_search_results(driver: webdriver.Chrome, timeout: int = 20) -> None:
    """Cho ket qua tim kiem hien thi."""
    log_step("Cho ket qua tim kiem hien thi")
    find_first_element(
        driver,
        [
            (By.CSS_SELECTOR, "a.item-content"),
            (By.XPATH, "//div[contains(@class,'item-restaurant')]")
        ],
        timeout=timeout,
        clickable=False,
    )


def open_first_shop(driver: webdriver.Chrome) -> None:
    """Mo quan dau tien trong ket qua tim kiem."""
    log_step("Chon quan dau tien")
    first_shop = find_first_element(
        driver,
        [
            (By.CSS_SELECTOR, "a.item-content"),
            (By.XPATH, "(//div[contains(@class,'item-restaurant')]//a)[1]"),
            (By.XPATH, "(//a[contains(@href,'shopeefood.vn')])[1]"),
        ],
        timeout=20,
        clickable=True,
    )
    safe_click(driver, first_shop)


def get_cart_count(driver: webdriver.Chrome) -> int:
    """Lay so luong item hien thi tren icon gio hang."""
    cart_badges = [
        (By.CSS_SELECTOR, "span.cart-badge"),
        (By.XPATH, "//div[contains(@class,'cart')]//span[contains(@class,'number') or contains(@class,'quantity')]")
    ]

    for locator in cart_badges:
        try:
            element = WebDriverWait(driver, 4).until(EC.presence_of_element_located(locator))
            text = element.text.strip()
            if text.isdigit():
                return int(text)
        except Exception:
            continue

    return 0


def add_first_food_to_cart(driver: webdriver.Chrome) -> None:
    """Them mon dau tien vao gio hang."""
    log_step("Chon mon dau tien va them vao gio")

    add_button_locators: List[Locator] = [
        (By.XPATH, "//button[contains(.,'Thêm') or contains(.,'Them') or normalize-space(.)='+']"),
        (By.XPATH, "//*[contains(@class,'btn-add') or contains(@class,'btn-plus')]") ,
        (By.XPATH, "//*[contains(@aria-label,'Thêm') or contains(@aria-label,'Them') or contains(@title,'Thêm') or contains(@title,'Them')]") ,
        (By.XPATH, "//*[self::button or self::a or self::div or self::span][.//i[contains(@class,'plus')] or .//*[contains(@class,'plus')]]"),
    ]

    wait = WebDriverWait(driver, 20)
    wait.until(lambda d: d.execute_script("return document.readyState") == "complete")

    for locator in add_button_locators:
        try:
            candidates = driver.find_elements(*locator)
            filtered: List[WebElement] = []

            for element in candidates:
                try:
                    if not element.is_displayed():
                        continue

                    if element.tag_name.lower() == "img":
                        continue

                    if element.tag_name.lower() in {"button", "a"} and not element.is_enabled():
                        continue

                    size = element.size
                    if size.get("width", 0) > 180 or size.get("height", 0) > 180:
                        continue

                    filtered.append(element)
                except Exception:
                    continue

            if not filtered:
                continue

            # Uu tien nut nho (icon +) thay vi container lon de tranh click vao anh.
            filtered.sort(key=lambda e: (e.size.get("width", 0) * e.size.get("height", 0), e.location.get("y", 0)))
            safe_click(driver, filtered[0])
            return
        except Exception:
            continue

    raise TimeoutException("Khong tim thay nut cong de them mon vao gio hang")


def open_cart(driver: webdriver.Chrome) -> None:
    """Mo khu vuc gio hang."""
    log_step("Mo gio hang")
    cart_element = find_first_element(
        driver,
        [
            (By.XPATH, "//div[contains(@class,'cart')]//*[contains(.,'Giỏ hàng') or contains(.,'Gio hang')]") ,
            (By.CSS_SELECTOR, "a[href*='cart'], div[class*='cart']"),
        ],
        timeout=15,
        clickable=True,
    )
    safe_click(driver, cart_element)


def go_to_checkout(driver: webdriver.Chrome) -> None:
    """Nhan nut dat hang/tiep tuc thanh toan."""
    log_step("Nhan nut dat hang hoac tiep tuc thanh toan")
    checkout_button = find_first_element(
        driver,
        [
            (By.XPATH, "//button[contains(.,'Đặt hàng') or contains(.,'Dat hang') or contains(.,'Thanh toán') or contains(.,'Thanh toan') or contains(.,'Tiếp tục') or contains(.,'Tiep tuc')]") ,
            (By.XPATH, "//a[contains(.,'Đặt hàng') or contains(.,'Dat hang') or contains(.,'Thanh toán') or contains(.,'Thanh toan')]") ,
            (By.CSS_SELECTOR, "button.btn-order, button.btn-confirm"),
        ],
        timeout=20,
        clickable=True,
    )
    safe_click(driver, checkout_button)


def verify_checkout_page(driver: webdriver.Chrome, timeout: int = 20) -> bool:
    """Xac nhan da den man checkout (khong thanh toan that)."""
    log_step("Verify da chuyen qua man checkout")

    def _is_checkout_loaded(web_driver: webdriver.Chrome) -> bool:
        url = web_driver.current_url.lower()
        if "checkout" in url or "payment" in url or "thanh-toan" in url:
            return True

        page_source = web_driver.page_source.lower()
        keywords = [
            "thong tin giao hang",
            "địa chỉ giao hàng",
            "dia chi giao hang",
            "phuong thuc thanh toan",
            "ghi chu",
        ]
        return any(keyword in page_source for keyword in keywords)

    try:
        WebDriverWait(driver, timeout).until(_is_checkout_loaded)
        return True
    except Exception:
        return False

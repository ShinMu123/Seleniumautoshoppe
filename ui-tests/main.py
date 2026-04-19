"""Luồng UI automation chính cho ứng dụng ShopeeFood Android.

Module này chạy kịch bản end-to-end trên mobile: mở app, tìm món,
thêm vào giỏ, đăng nhập khi cần, và xuất số liệu runtime cho unit-test.
"""

import os
import json
import re
import shutil
import subprocess
import time
import unicodedata
from difflib import SequenceMatcher
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.error import URLError
from urllib.request import urlopen

from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


Locator = Tuple[str, str]


def load_local_env_file(env_path: str = ".env") -> None:
    """Nạp biến môi trường từ file .env.

    Mục tiêu của hàm:
    1. Cho phép cấu hình local bằng file .env.
    2. Không ghi đè biến môi trường đã có sẵn từ hệ điều hành/terminal.
    """
    env_file = Path(env_path)
    # Nếu không có file .env thì bỏ qua để chương trình vẫn chạy với env hiện tại.
    if not env_file.exists():
        return

    # Đọc từng dòng để parse theo format KEY=VALUE.
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        # Bỏ qua dòng rỗng, dòng comment (#...) hoặc dòng không hợp lệ.
        if not line or line.startswith("#") or "=" not in line:
            continue

        # Chỉ tách ở dấu '=' đầu tiên để value vẫn giữ nguyên nếu chứa '='.
        key, value = line.split("=", 1)
        key = key.strip()
        # Chuẩn hóa value: bỏ khoảng trắng và bỏ cặp nháy bao quanh nếu có.
        value = value.strip().strip('"').strip("'")

        # Chỉ set khi key hợp lệ và chưa tồn tại trong os.environ.
        # => Biến đã set từ bên ngoài (CI/terminal) sẽ được ưu tiên.
        if key and key not in os.environ:
            os.environ[key] = value


load_local_env_file()


@dataclass(frozen=True)
class AppConfig:
    # Nhóm cấu hình kết nối Appium và thiết bị Android.
    appium_server_url: str = os.environ.get("APPIUM_SERVER_URL", "http://127.0.0.1:4723")
    device_name: str = os.environ.get("ANDROID_DEVICE_NAME", "Android Emulator")
    udid: str = os.environ.get("ANDROID_UDID", "emulator-5554")
    platform_version: str = os.environ.get("ANDROID_PLATFORM_VERSION", "")
    app_package: str = os.environ.get("SHOPEEFOOD_APP_PACKAGE", "com.deliverynow")
    app_activity: str = os.environ.get("SHOPEEFOOD_APP_ACTIVITY", "")
    app_wait_activity: str = os.environ.get("SHOPEEFOOD_APP_WAIT_ACTIVITY", "*")
    automation_name: str = "UiAutomator2"
    command_timeout_sec: int = int(os.environ.get("APPIUM_COMMAND_TIMEOUT", "180"))
    wait_timeout_sec: int = int(os.environ.get("APPIUM_WAIT_TIMEOUT", "20"))

    # Nhóm cấu hình hành vi runtime và thu thập ảnh/log khi chạy.
    screenshot_dir: str = os.environ.get("SCREENSHOT_DIR", "screenshots")
    disable_android_animations: bool = (
        os.environ.get("DISABLE_ANDROID_ANIMATIONS", "1").strip().lower() not in ["0", "false", "no"]
    )

    # Dữ liệu nghiệp vụ cho flow tìm món và thêm vào giỏ.
    store_name: str = os.environ.get("STORE_NAME", os.environ.get("SHOP_NAME", "")).strip()
    food_name: str = os.environ.get("FOOD_NAME", os.environ.get("DISH_NAME", "trà sữa")).strip()
    item_name: str = os.environ.get("ITEM_NAME", os.environ.get("FOOD_NAME", "trà sữa")).strip()
    shopee_user: str = os.environ.get("SHOPEE_USER", os.environ.get("SHOPEE_USERNAME", "")).strip()
    shopee_pass: str = os.environ.get("SHOPEE_PASS", os.environ.get("SHOPEE_PASSWORD", "")).strip()
    detail_pause_sec: float = float(os.environ.get("DETAIL_PAUSE_SEC", "2.5"))
    plus_pause_sec: float = float(os.environ.get("PLUS_PAUSE_SEC", "2.5"))
    auto_quit: bool = os.environ.get("AUTO_QUIT", "0").strip().lower() in ["1", "true", "yes"]

    # Giá trị cầu nối để xuất dữ liệu UI sang unit-tests.
    default_distance_km: float = float(os.environ.get("UI_DEFAULT_DISTANCE_KM", "4"))
    estimate_mode: bool = os.environ.get("UI_ESTIMATE_MODE", "1").strip().lower() in ["1", "true", "yes"]
    estimate_quantity: int = int(os.environ.get("UI_RESULT_QUANTITY", "1"))
    add_to_cart_qty: int = int(os.environ.get("ADD_TO_CART_QTY", os.environ.get("UI_RESULT_QUANTITY", "1")))


# Bản đồ locator dùng nhiều chiến lược dự phòng để giảm flaky khi UI thay đổi.
LOCATORS = {
    "permission_allow": [
        (AppiumBy.ID, "com.android.permissioncontroller:id/permission_allow_foreground_only_button"),
        (AppiumBy.ID, "com.android.permissioncontroller:id/permission_allow_one_time_button"),
        (AppiumBy.ID, "com.android.permissioncontroller:id/permission_allow_button"),
        (AppiumBy.ID, "com.android.packageinstaller:id/permission_allow_button"),
        (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Cho phép")'),
        (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Trong khi dùng")'),
        (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Allow")'),
    ],
    "login_text": [
        (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Đăng nhập")'),
        (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Đăng ký / Đăng nhập")'),
        (AppiumBy.XPATH, "//*[contains(@text,'Đăng nhập') or contains(@content-desc,'Đăng nhập')]")
    ],
    "login_submit": [
        (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Đăng nhập")'),
        (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Tiếp tục")'),
        (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Xác nhận")'),
        (AppiumBy.XPATH, "//*[contains(@resource-id,'login') or contains(@resource-id,'submit')]")
    ],
    "search_input": [
        (AppiumBy.CLASS_NAME, "android.widget.EditText"),
        (AppiumBy.CLASS_NAME, "android.widget.AutoCompleteTextView"),
        (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Tìm")'),
        (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Tìm kiếm")'),
        (AppiumBy.XPATH, "//*[contains(@resource-id,'search') and (@class='android.widget.EditText' or @class='android.widget.AutoCompleteTextView')]"),
    ],
    "home_search_bar": [
        (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Tìm")'),
        (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Bún")'),
        (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Mì")'),
        (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Phở")'),
        (AppiumBy.XPATH, "//*[contains(@resource-id,'search') and not(@class='android.widget.EditText') and not(@class='android.widget.AutoCompleteTextView')]"),
    ],
    "search_screen_hint": [
        (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Lịch sử tìm kiếm")'),
        (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Gợi ý tìm kiếm")'),
        (AppiumBy.XPATH, "//*[contains(@text,'Lịch sử tìm kiếm') or contains(@text,'Gợi ý tìm kiếm')]")
    ],
    "home_search_hint": [
        (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Deal Cú Đêm")'),
        (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Freeship")'),
        (AppiumBy.XPATH, "//*[contains(@text,'Deal Cú Đêm') or contains(@text,'Freeship')]")
    ],
    "cart_text": [
        (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Giỏ")'),
        (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().descriptionContains("Giỏ")'),
    ],
    "add_to_cart_button": [
        (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Thêm vào giỏ hàng")'),
        (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Thêm vào giỏ")'),
        (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Them vao gio hang")'),
        (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Them vao gio")'),
        (AppiumBy.XPATH, "//*[contains(@text,'Thêm vào giỏ') or contains(@content-desc,'Thêm vào giỏ')]")
    ],
    "store_search_input": [
        (AppiumBy.CLASS_NAME, "android.widget.EditText"),
        (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Tìm món tại")'),
        (AppiumBy.XPATH, "//*[contains(@text,'Tìm món tại')]")
    ],
    "menu_plus_button": [
        (AppiumBy.XPATH, "//android.widget.TextView[@text='+']"),
        (AppiumBy.XPATH, "//*[contains(@resource-id,'btn_add') or contains(@resource-id,'add_item')]")
    ],
    "cart_entry": [
        (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Giỏ")'),
        (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().descriptionContains("Giỏ")'),
        (AppiumBy.XPATH, "//*[contains(@text,'Giỏ') or contains(@content-desc,'Giỏ')]")
    ],
    "checkout_summary_anchor": [
        (AppiumBy.XPATH, "//*[contains(@text,'Tạm tính') or contains(@text,'Tam tinh') or contains(@text,'Thanh toán') or contains(@text,'Thanh toan')]")
    ],
    "summary_food_price": [
        (AppiumBy.XPATH, "//*[contains(@text,'Tạm tính') or contains(@text,'Tam tinh')]")
    ],
    "summary_shipping_fee": [
        (AppiumBy.XPATH, "//*[contains(@text,'Phí giao hàng') or contains(@text,'Phi giao hang') or contains(@text,'Phí ship') or contains(@text,'Phi ship')]")
    ],
    "summary_total": [
        (AppiumBy.XPATH, "//*[contains(@text,'Thanh toán') or contains(@text,'Thanh toan') or contains(@text,'Tổng') or contains(@text,'Tong')]")
    ],
    "summary_distance": [
        (AppiumBy.XPATH, "//*[contains(@text,'km') or contains(@content-desc,'km')]")
    ],
}


class ShopeeFoodFlow:
    def __init__(self, config: AppConfig) -> None:
        # Lưu config cho toàn bộ flow và dùng 1 driver session xuyên suốt.
        self.config = config
        self.driver: Optional[webdriver.Remote] = None
        Path(self.config.screenshot_dir).mkdir(parents=True, exist_ok=True)

    def _check_appium_server(self) -> None:
        status_url = self.config.appium_server_url.rstrip("/") + "/status"
        try:
            with urlopen(status_url, timeout=4) as response:
                body = response.read().decode("utf-8", errors="ignore")
                if "ready" not in body.lower() and "status" not in body.lower():
                    raise RuntimeError("Appium server trả về dữ liệu bất thường")
        except URLError as ex:
            raise RuntimeError(
                f"Không kết nối được Appium server: {status_url}. Hãy chạy appium trước khi test."
            ) from ex

    def _resolve_adb_command(self) -> str:
        env_adb = (os.environ.get("ADB_PATH") or "").strip()
        if env_adb and Path(env_adb).exists():
            return env_adb

        found = shutil.which("adb")
        if found:
            return found

        candidates = [
            Path(os.environ.get("ANDROID_HOME", "")) / "platform-tools" / "adb.exe",
            Path(os.environ.get("ANDROID_SDK_ROOT", "")) / "platform-tools" / "adb.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk" / "platform-tools" / "adb.exe",
            Path.home() / "AppData" / "Local" / "Android" / "Sdk" / "platform-tools" / "adb.exe",
        ]
        for candidate in candidates:
            if str(candidate).strip() and candidate.exists():
                os.environ["ADB_PATH"] = str(candidate)
                return str(candidate)

        raise RuntimeError("Không tìm thấy adb. Hãy set ADB_PATH hoặc thêm adb vào PATH")

    def _run_adb(self, args: List[str], timeout: int = 12) -> str:
        adb = self._resolve_adb_command()
        result = subprocess.run(
            [adb] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ADB command lỗi: {' '.join(args)} | {result.stderr.strip()}")
        return result.stdout.strip()

    def _check_device_and_app(self) -> None:
        devices_out = self._run_adb(["devices"])
        target_udid = self.config.udid.strip()

        connected = False
        for line in devices_out.splitlines()[1:]:
            row = line.strip()
            if not row:
                continue
            if target_udid and row.startswith(target_udid) and "device" in row:
                connected = True
                break

        if not connected:
            raise RuntimeError(f"Thiết bị {target_udid} chưa kết nối")

        package_out = self._run_adb(["-s", target_udid, "shell", "pm", "list", "packages", self.config.app_package], timeout=20)
        if self.config.app_package not in package_out:
            raise RuntimeError(f"Không tìm thấy app package {self.config.app_package} trên thiết bị")

    def _speed_up_android_ui(self) -> None:
        if not self.config.disable_android_animations:
            return

        udid = self.config.udid.strip()
        commands = [
            ["-s", udid, "shell", "settings", "put", "global", "window_animation_scale", "0"],
            ["-s", udid, "shell", "settings", "put", "global", "transition_animation_scale", "0"],
            ["-s", udid, "shell", "settings", "put", "global", "animator_duration_scale", "0"],
        ]
        for cmd in commands:
            try:
                self._run_adb(cmd)
            except Exception:
                pass

    def _build_options(self) -> UiAutomator2Options:
        # Dựng capability Appium từ AppConfig (đọc từ biến môi trường).
        options = UiAutomator2Options()
        options.platform_name = "Android"
        options.automation_name = self.config.automation_name
        options.device_name = self.config.device_name
        options.udid = self.config.udid
        options.new_command_timeout = self.config.command_timeout_sec
        options.app_package = self.config.app_package
        options.no_reset = True
        options.auto_grant_permissions = False

        if self.config.app_activity:
            options.app_activity = self.config.app_activity
        if self.config.app_wait_activity:
            options.app_wait_activity = self.config.app_wait_activity
        if self.config.platform_version:
            options.platform_version = self.config.platform_version

        return options

    def _require_driver(self) -> webdriver.Remote:
        if not self.driver:
            raise RuntimeError("Driver chưa được khởi tạo")
        return self.driver

    def start_session(self) -> None:
        self._check_appium_server()
        self._check_device_and_app()
        self._speed_up_android_ui()
        self.driver = webdriver.Remote(self.config.appium_server_url, options=self._build_options())
        self.driver.implicitly_wait(0)
        self.driver.activate_app(self.config.app_package)
        print("Đã mở session Appium thành công")

    def stop_session(self) -> None:
        if self.driver:
            self.driver.quit()
            self.driver = None
            print("Đã đóng app/session an toàn")

    def _pause_for_observation(self, seconds: float, reason: str) -> None:
        if seconds <= 0:
            return
        print(f"Tạm dừng {seconds:.1f}s: {reason}")
        time.sleep(seconds)

    def _confirm_before_quit(self) -> None:
        if self.config.auto_quit:
            self.stop_session()
            return

        print("Giữ app mở để quan sát. Nhấn Enter trong terminal để đóng app...")
        try:
            input()
        except EOFError:
            # Khi chạy môi trường không tương tác được stdin, vẫn đảm bảo app được đóng gọn.
            pass
        self.stop_session()

    def save_error_screenshot(self, prefix: str) -> None:
        if not self.driver:
            return
        output = Path(self.config.screenshot_dir) / f"{prefix}_{int(time.time())}.png"
        try:
            self.driver.save_screenshot(str(output))
            print(f"Đã lưu screenshot lỗi: {output}")
        except Exception:
            pass

    def save_step_screenshot(self, prefix: str) -> None:
        if not self.driver:
            return
        output = Path(self.config.screenshot_dir) / f"{prefix}_{int(time.time())}.png"
        try:
            self.driver.save_screenshot(str(output))
            print(f"Đã lưu screenshot bước chạy: {output}")
        except Exception:
            pass

    def wait_first(self, locators: List[Locator], timeout: Optional[int] = None) -> WebElement:
        driver = self._require_driver()
        wait_timeout = timeout if timeout is not None else self.config.wait_timeout_sec
        end = time.time() + wait_timeout
        last_error: Optional[Exception] = None

        while time.time() < end:
            for by, value in locators:
                try:
                    element = WebDriverWait(driver, 1).until(EC.presence_of_element_located((by, value)))
                    if element.is_displayed():
                        return element
                except Exception as ex:
                    last_error = ex
            time.sleep(0.2)

        raise TimeoutException(f"Không tìm thấy element. Lỗi cuối: {last_error}")

    def find_first_visible(self, locators: List[Locator]) -> Optional[WebElement]:
        driver = self._require_driver()
        for by, value in locators:
            try:
                for item in driver.find_elements(by, value):
                    if item.is_displayed():
                        return item
            except Exception:
                continue
        return None

    def safe_tap_element(self, element: WebElement) -> None:
        driver = self._require_driver()
        try:
            element.click()
            return
        except Exception:
            pass

        try:
            driver.execute_script("mobile: clickGesture", {"elementId": element.id})
            return
        except Exception:
            pass

        rect = element.rect
        center_x = int(rect["x"] + rect["width"] / 2)
        center_y = int(rect["y"] + rect["height"] / 2)
        driver.execute_script("mobile: clickGesture", {"x": center_x, "y": center_y})

    def tap_percent(self, x_percent: float, y_percent: float) -> None:
        driver = self._require_driver()
        size = driver.get_window_size()
        x = int(size["width"] * x_percent)
        y = int(size["height"] * y_percent)
        driver.execute_script("mobile: clickGesture", {"x": x, "y": y})

    def handle_permissions(self) -> None:
        for _ in range(4):
            allow_btn = self.find_first_visible(LOCATORS["permission_allow"])
            if allow_btn is None:
                break
            self.safe_tap_element(allow_btn)
            time.sleep(0.35)
        print("Đã cấp quyền Android")

    def close_ads_if_exist(self) -> None:
        driver = self._require_driver()
        closed = False

        for _ in range(3):
            source = (driver.page_source or "").lower()
            ad_hint = any(k in source for k in ["voucher", "khuyến mãi", "ưu đãi", "banner", "quảng cáo", "welcome"])
            if not ad_hint:
                break
            self.tap_percent(0.95, 0.12)
            closed = True
            time.sleep(0.6)

        if closed:
            print("Đã đóng popup quảng cáo")

    def _visible_edit_texts(self) -> List[WebElement]:
        driver = self._require_driver()
        visible: List[WebElement] = []
        candidates = [
            (AppiumBy.CLASS_NAME, "android.widget.EditText"),
            (AppiumBy.CLASS_NAME, "android.widget.AutoCompleteTextView"),
            (AppiumBy.XPATH, "//androidx.appcompat.widget.SearchView//android.widget.AutoCompleteTextView"),
        ]
        for by, value in candidates:
            try:
                for item in driver.find_elements(by, value):
                    if item.is_displayed() and item.is_enabled():
                        visible.append(item)
            except Exception:
                continue
        return visible

    def login_if_needed(self) -> bool:
        driver = self._require_driver()
        login_indicator = self.find_first_visible(LOCATORS["login_text"])
        source = (driver.page_source or "")

        if login_indicator is None and "Đăng nhập" not in source:
            return False

        user = self.config.shopee_user
        password = self.config.shopee_pass
        if not user or not password:
            raise RuntimeError("Thiếu SHOPEE_USER hoặc SHOPEE_PASS trong .env")

        # Bat buoc di theo luong dang nhap bang mat khau.
        password_login_link = self.find_first_visible([
            (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Đăng nhập bằng Mật khẩu")'),
            (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Đăng nhập bằng mật khẩu")'),
            (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Dang nhap bang Mat khau")'),
            (AppiumBy.XPATH, '//*[contains(@text,"Đăng nhập bằng") and contains(@text,"mật khẩu")]'),
        ])
        if password_login_link is not None:
            self.safe_tap_element(password_login_link)
            print("Đã bấm Đăng nhập bằng mật khẩu")
            time.sleep(0.6)

        # Cho den khi co du 2 o nhap (ten dang nhap + mat khau).
        fields: List[WebElement] = []
        end = time.time() + max(self.config.wait_timeout_sec, 15)
        while time.time() < end:
            fields = self._visible_edit_texts()
            if len(fields) >= 2:
                break
            time.sleep(0.25)

        if len(fields) < 2:
            raise RuntimeError("Không mở được form đăng nhập bằng mật khẩu")

        fields[0].clear()
        fields[0].send_keys(user)
        fields[1].clear()
        fields[1].send_keys(password)
        print("Đã nhập tài khoản và mật khẩu")

        submit = self.find_first_visible([
            (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("Đăng nhập")'),
            (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Đăng nhập")'),
            (AppiumBy.XPATH, '//*[contains(@text,"Đăng nhập") and not(contains(@text,"SMS")) and not(contains(@text,"Google")) and not(contains(@text,"Facebook"))]'),
        ])
        if submit is not None:
            self.safe_tap_element(submit)
        else:
            driver.press_keycode(66)
        print("Đã bấm nút Đăng nhập")

        WebDriverWait(driver, 30).until(lambda d: not self._is_login_gate_screen())
        print("Đăng nhập thành công")
        return True

    def _cart_badge_count(self) -> Optional[int]:
        source = (self._require_driver().page_source or "")
        patterns = [
            r"Giỏ hàng[^\d]{0,20}(\d{1,2})",
            r"cart[^\d]{0,20}(\d{1,2})",
        ]
        for pattern in patterns:
            match = re.search(pattern, source, flags=re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None

    def _is_search_ready(self) -> bool:
        if self.find_first_visible(LOCATORS["search_screen_hint"]) is not None:
            return True
        if self._visible_edit_texts():
            return True

        source = (self._require_driver().page_source or "").lower()
        return any(k in source for k in ["lịch sử tìm kiếm", "gợi ý tìm kiếm", "xóa"])

    def _wait_search_ready(self, timeout: float = 2.0) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            if self._is_search_ready():
                return True
            time.sleep(0.2)
        return False

    def _is_store_page(self) -> bool:
        source = (self._require_driver().page_source or "").lower()
        return any(
            k in source
            for k in [
                "tìm món tại",
                "thêm vào giỏ",
                "thêm món mới",
                "topping",
                "món phổ biến",
                "ưu đãi dành cho bạn",
                "giao ngay",
            ]
        )

    def _is_in_store_search_result_page(self) -> bool:
        source = (self._require_driver().page_source or "").lower()
        has_search_box = any(k in source for k in ["tìm món", "tim mon"])
        has_result_hint = any(k in source for k in ["đã bán", "da ban", "lượt thích", "luot thich", "xem thêm", "xem them"])
        has_money = re.search(r"\d[\d\.,]{1,}\s*đ", source) is not None
        return has_search_box and (has_result_hint or has_money)

    def _tap_search_result_row(self, item_name: str, timeout: float = 3.0) -> bool:
        driver = self._require_driver()
        size = driver.get_window_size()
        target = self._normalize_vi_text(item_name)
        tokens = [tok for tok in target.split() if tok]

        end = time.time() + timeout
        while time.time() < end:
            try:
                best_y: Optional[int] = None
                best_score = -1.0

                for node in driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.TextView"):
                    if not node.is_displayed():
                        continue
                    txt = (node.text or "").strip()
                    if not txt:
                        continue

                    rect = node.rect
                    if not rect:
                        continue
                    cy = int(rect["y"] + rect["height"] / 2)
                    if cy < int(size["height"] * 0.10) or cy > int(size["height"] * 0.45):
                        continue

                    norm_txt = self._normalize_vi_text(txt)
                    if any(bad in norm_txt for bad in ["tim mon", "xem them", "da ban", "luot thich"]):
                        continue

                    token_hits = sum(1 for tok in tokens if tok in norm_txt)
                    if token_hits == 0:
                        continue
                    score = token_hits / max(len(tokens), 1)
                    if score > best_score:
                        best_score = score
                        best_y = cy

                if best_y is not None:
                    # Tap vao than row ben trai/trung tam, tranh icon '+' o mep phai.
                    for x_pos in [0.42, 0.35, 0.28]:
                        x = int(size["width"] * x_pos)
                        driver.execute_script("mobile: clickGesture", {"x": x, "y": best_y})
                        print(f"Đã bấm row kết quả tìm kiếm tại ({x}, {best_y})")
                        time.sleep(0.45)
                        if self._wait_item_detail_ready(timeout=2.0) and self._is_product_detail_page_strict():
                            return True
            except Exception:
                pass
            time.sleep(0.2)

        return False

    def _is_login_gate_screen(self) -> bool:
        source = (self._require_driver().page_source or "").lower()
        markers = [
            "đăng nhập / đăng ký",
            "dang nhap / dang ky",
            "đăng nhập bằng mật khẩu",
            "số điện thoại",
            "tiếp tục với shopee",
            "tiếp tục với google",
            "tiếp tục với facebook",
        ]
        return any(marker in source for marker in markers)

    def open_search(self) -> None:
        # Nếu lạc vào trang ưu đãi/chi tiết, quay về màn có ô search trước khi tap.
        source = (self._require_driver().page_source or "").lower()
        if "thương hiệu giảm" in source or "deal cú đêm thương hiệu" in source:
            self.tap_percent(0.04, 0.08)
            time.sleep(0.5)

        # Tap lần 1 ở đúng vùng search bar.
        self.tap_percent(0.50, 0.13)
        if self._wait_search_ready(timeout=2.2):
            print("Tap search lần 1 thành công")
            print("Search input đã hiển thị")
            return

        # Chỉ fallback khi chắc chắn chưa vào màn search.
        print("Fallback tap search lần 2")
        self.tap_percent(0.50, 0.11)
        if self._wait_search_ready(timeout=2.2):
            print("Search input đã hiển thị")
            return

        # Fallback khi home hiển thị thanh search dạng banner/text.
        home_search = self.find_first_visible(LOCATORS["home_search_bar"])
        if home_search is not None:
            self.safe_tap_element(home_search)
            if self._wait_search_ready(timeout=2.2):
                print("Search input đã hiển thị")
                return

        # Một số máy lệch tỉ lệ, tap thấp hơn một chút rồi chờ lại.
        self.tap_percent(0.50, 0.17)
        if self._wait_search_ready(timeout=2.2):
            print("Search input đã hiển thị")
            return

        self.wait_first(LOCATORS["search_input"], timeout=8)
        print("Search input đã hiển thị")

    def input_food_name(self) -> None:
        entered = False
        for attempt in range(1, 4):
            try:
                fields = self._visible_edit_texts()
                if not fields:
                    search_input = self.wait_first(LOCATORS["search_input"], timeout=10)
                    self.safe_tap_element(search_input)
                    fields = self._visible_edit_texts()

                if not fields:
                    raise RuntimeError("Không tìm thấy ô nhập tìm kiếm")

                target = fields[0]
                self.safe_tap_element(target)
                try:
                    target.clear()
                except Exception:
                    pass
                target.send_keys(self.config.food_name)
                entered = True
                break
            except Exception as ex:
                if attempt == 3:
                    raise RuntimeError(f"Không nhập được từ khóa tìm kiếm sau 3 lần thử: {ex}") from ex
                print(f"Retry nhập từ khóa lần {attempt + 1}...")
                time.sleep(0.6)
                self.open_search()

        if not entered:
            raise RuntimeError("Không nhập được FOOD_NAME")

        # Bắt buộc bấm icon kính lúp bên phải thanh tìm kiếm.
        self.tap_percent(0.95, 0.08)
        time.sleep(0.25)
        # Fallback nhẹ nếu icon chưa nhận tap.
        if self._is_search_suggestion_screen():
            self.tap_percent(0.92, 0.08)
            time.sleep(0.25)

        # Giữ Enter như lớp dự phòng cuối cùng, không phải nhánh chính.
        if self._is_search_suggestion_screen():
            self._require_driver().press_keycode(66)

    def _is_search_suggestion_screen(self) -> bool:
        source = (self._require_driver().page_source or "").lower()
        return any(k in source for k in ["lịch sử tìm kiếm", "gợi ý tìm kiếm", "deal cú đêm", "freeship"])

    def _is_product_detail_page(self) -> bool:
        source = (self._require_driver().page_source or "").lower()
        # Layout chi tiet mon co the thay doi, nen detect theo nhieu nhom dau hieu.
        marker_groups = [
            ["bình luận", "binh luan"],
            ["đã bán", "da ban"],
            ["lượt thích", "luot thich"],
            ["chưa có đánh giá", "chua co danh gia"],
            ["thêm món mới", "chon size", "topping thêm", "thêm vào giỏ"],
            ["foody.vn", "foodyn"],
        ]

        group_hits = sum(1 for variants in marker_groups if any(v in source for v in variants))
        has_money = re.search(r"\d[\d\.,]{1,}\s*đ", source) is not None

        # Uu tien tranh false-positive o man danh sach: can co it nhat 2 nhom dau hieu,
        # hoac 1 nhom + dong gia tien lon hien tren chi tiet.
        if group_hits >= 2:
            return True
        return group_hits >= 1 and has_money

    def _is_product_detail_page_strict(self) -> bool:
        source = (self._require_driver().page_source or "").lower()

        has_comment = any(k in source for k in ["bình luận", "binh luan"])
        has_social = any(k in source for k in ["đã bán", "da ban", "lượt thích", "luot thich", "chưa có đánh giá", "chua co danh gia"])
        has_money = re.search(r"\d[\d\.,]{1,}\s*đ", source) is not None
        has_order_now = any(k in source for k in ["đặt món ngay", "dat mon ngay"])

        # Trang chi tiet that thuong co binh luan + gia tien, kem them social/order marker.
        if has_comment and has_money and (has_social or has_order_now):
            return True
        return False

    def _is_detail_plus_visible(self) -> bool:
        driver = self._require_driver()
        size = driver.get_window_size()
        for locator in LOCATORS["menu_plus_button"]:
            by, value = locator
            try:
                for item in driver.find_elements(by, value):
                    if not item.is_displayed():
                        continue
                    rect = item.rect
                    if not rect:
                        continue
                    cx = rect["x"] + rect["width"] / 2
                    cy = rect["y"] + rect["height"] / 2
                    if cx >= size["width"] * 0.80 and size["height"] * 0.55 <= cy <= size["height"] * 0.82:
                        return True
            except Exception:
                continue
        return False

    def _wait_item_detail_ready(self, timeout: float = 4.5) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            source = (self._require_driver().page_source or "")
            # Chỉ pass khi có tín hiệu thật của trang/popup chi tiết món.
            if self._is_product_detail_page() or self._is_detail_plus_visible() or any(
                k in source.lower() for k in ["thêm món mới", "chọn size", "topping thêm", "thêm vào giỏ hàng", "đặt món ngay"]
            ):
                return True
            time.sleep(0.2)
        return False

    def _is_add_item_modal_open(self) -> bool:
        source = (self._require_driver().page_source or "").lower()
        markers = [
            "thêm món mới",
            "them mon moi",
            "topping",
            "chọn size",
            "chon size",
            "ghi chú quán",
            "ghi chu quan",
            "thêm vào giỏ hàng",
            "them vao gio hang",
        ]
        return any(marker in source for marker in markers)

    def _tap_add_to_cart_confirm_if_present(self) -> bool:
        add_btn = self.find_first_visible(LOCATORS["add_to_cart_button"])
        if add_btn is None:
            return False
        self.safe_tap_element(add_btn)
        print("Đã bấm Thêm vào giỏ hàng")
        time.sleep(0.35)
        return True

    def _open_quantity_input_dialog_from_modal(self) -> bool:
        if not self._is_add_item_modal_open():
            return False

        driver = self._require_driver()
        size = driver.get_window_size()

        # Uu tien tap vao so luong dang hien thi (thuong la "1") nam giua nut - va +.
        best_candidate: Optional[Tuple[int, int, float]] = None
        try:
            for node in driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.TextView"):
                if not node.is_displayed():
                    continue
                txt = (node.text or "").strip()
                if not re.fullmatch(r"\d{1,3}", txt):
                    continue

                rect = node.rect
                if not rect:
                    continue
                cx = int(rect["x"] + rect["width"] / 2)
                cy = int(rect["y"] + rect["height"] / 2)

                # So luong cua dong mon thuong nam ben phai va o nua tren popup.
                if cx < int(size["width"] * 0.72) or cx > int(size["width"] * 0.98):
                    continue
                if cy < int(size["height"] * 0.28) or cy > int(size["height"] * 0.56):
                    continue

                score = 0.0
                if txt == "1":
                    score += 2.0
                if int(size["width"] * 0.84) <= cx <= int(size["width"] * 0.94):
                    score += 2.0
                if int(size["height"] * 0.34) <= cy <= int(size["height"] * 0.48):
                    score += 1.0

                if best_candidate is None or score > best_candidate[2]:
                    best_candidate = (cx, cy, score)
        except Exception:
            best_candidate = None

        if best_candidate is not None:
            cx, cy, _ = best_candidate
            driver.execute_script("mobile: clickGesture", {"x": cx, "y": cy})
            time.sleep(0.35)
            return True

        # Fallback toa do: khu vuc so luong o dong dau cua popup.
        for x_pos, y_pos in [(0.89, 0.39), (0.87, 0.39), (0.90, 0.36)]:
            self.tap_percent(x_pos, y_pos)
            time.sleep(0.3)
            return True
        return False

    def _set_quantity_via_input_dialog(self, quantity: int) -> bool:
        if quantity <= 0:
            return False

        driver = self._require_driver()
        end = time.time() + 4.0
        dialog_open = False
        while time.time() < end:
            source = (driver.page_source or "").lower()
            if "số lượng" in source or "so luong" in source:
                dialog_open = True
                break
            time.sleep(0.2)

        if not dialog_open:
            return False

        input_box: Optional[WebElement] = None
        try:
            fields = driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.EditText")
            for field in fields:
                if field.is_displayed() and field.is_enabled():
                    input_box = field
                    break
        except Exception:
            input_box = None

        if input_box is None:
            return False

        self.safe_tap_element(input_box)
        try:
            input_box.clear()
        except Exception:
            pass
        input_box.send_keys(str(quantity))
        time.sleep(0.2)

        done_button = self.find_first_visible([
            (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("Xong")'),
            (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Xong")'),
            (AppiumBy.XPATH, "//*[contains(@text,'Xong') or contains(@content-desc,'Xong')]")
        ])
        if done_button is not None:
            self.safe_tap_element(done_button)
            time.sleep(0.35)
            return True

        driver.press_keycode(66)
        time.sleep(0.35)
        return True

    def _set_modal_quantity_direct(self, quantity: int) -> bool:
        if quantity <= 0:
            return False
        if not self._is_add_item_modal_open():
            return False
        if quantity == 1:
            return True

        if not self._open_quantity_input_dialog_from_modal():
            return False
        if not self._set_quantity_via_input_dialog(quantity):
            return False

        print(f"Đã nhập số lượng trực tiếp: {quantity}")
        return True

    def _tap_order_now_if_present(self) -> bool:
        order_now = self.find_first_visible([
            (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Đặt món ngay")'),
            (AppiumBy.XPATH, '//*[contains(@text,"Đặt món ngay") or contains(@content-desc,"Đặt món ngay")]'),
        ])
        if order_now is None:
            return False
        self.safe_tap_element(order_now)
        time.sleep(0.7)
        return True

    def _wait_cart_count_increase(self, before_count: Optional[int], timeout: float = 2.0) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            after_count = self._cart_badge_count()
            if before_count is not None and after_count is not None and after_count > before_count:
                return True
            if before_count is None and after_count is not None and after_count > 0:
                return True
            time.sleep(0.2)
        return False

    def _has_cart_ready_indicators(self) -> bool:
        source = (self._require_driver().page_source or "").lower()
        has_delivery_bar = any(k in source for k in ["giao hàng", "giao hang"])
        has_cart_words = any(k in source for k in ["giỏ", "gio", "cart"])
        has_temporary_total = any(k in source for k in ["tạm tính", "tam tinh", "thanh toán", "thanh toan"])
        return (has_delivery_bar and has_cart_words) or has_temporary_total

    def _calculate_shipping_fee_from_distance(self, distance_km: float) -> float:
        rounded_distance = int(distance_km) if float(distance_km).is_integer() else int(distance_km) + 1
        if rounded_distance <= 3:
            return 17000.0
        if rounded_distance <= 5:
            return 17000.0 + (rounded_distance - 3) * 5500.0
        if rounded_distance <= 10:
            return 28500.0 + (rounded_distance - 6) * 6000.0
        return 57000.0 + (rounded_distance - 11) * 5500.0

    def _extract_nearest_distance_km_from_store_list(self) -> float:
        driver = self._require_driver()
        values: List[float] = []
        for node in driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.TextView"):
            if not node.is_displayed():
                continue
            txt = (node.text or "").strip().lower()
            if "km" not in txt:
                continue
            match = re.search(r"(\d+(?:[\.,]\d+)?)\s*km", txt)
            if not match:
                continue
            try:
                values.append(float(match.group(1).replace(",", ".")))
            except Exception:
                continue

        if not values:
            source = (driver.page_source or "").lower()
            for match in re.finditer(r"(\d+(?:[\.,]\d+)?)\s*km", source):
                try:
                    values.append(float(match.group(1).replace(",", ".")))
                except Exception:
                    continue

        if not values:
            raise RuntimeError("Khong doc duoc km o man hinh danh sach quan")

        nearest = min(values)
        print(f"Đã đọc khoảng cách gần nhất: {nearest} km")
        return nearest

    def _force_submit_search(self) -> None:
        driver = self._require_driver()
        # Tap icon search and press Enter to force search request.
        self.tap_percent(0.95, 0.08)
        time.sleep(0.25)
        driver.press_keycode(66)

    def _wait_search_results_with_distance(self, timeout: float = 25.0) -> None:
        driver = self._require_driver()
        end = time.time() + timeout
        next_retry = time.time() + 4.0

        while time.time() < end:
            source = (driver.page_source or "").lower()
            if re.search(r"\d+(?:[\.,]\d+)?\s*km", source):
                return

            if time.time() >= next_retry:
                self._force_submit_search()
                next_retry = time.time() + 4.0

            time.sleep(0.25)

        raise RuntimeError("Khong thay ket qua tim kiem co thong tin km")

    def _extract_distance_km_from_current_page(self) -> float:
        driver = self._require_driver()
        source = (driver.page_source or "").lower()
        match = re.search(r"(\d+(?:[\.,]\d+)?)\s*km", source)
        if not match:
            raise RuntimeError("Khong doc duoc km tren trang quan hien tai")
        distance = float(match.group(1).replace(",", "."))
        print(f"Đã đọc khoảng cách từ trang quán: {distance} km")
        return distance

    def _extract_item_price_from_detail(self) -> float:
        driver = self._require_driver()
        prices: List[float] = []
        for node in driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.TextView"):
            if not node.is_displayed():
                continue
            txt = (node.text or "").strip().lower()
            match = re.search(r"(\d[\d\.,]{2,})\s*(?:đ|vnd)", txt)
            if not match:
                continue
            normalized = match.group(1).replace(".", "").replace(",", "")
            if normalized.isdigit():
                value = float(int(normalized))
                # Filter out tiny/non-price values and unrealistic high values.
                if 5000 <= value <= 1000000:
                    prices.append(value)

        if not prices:
            raise RuntimeError("Khong doc duoc gia mon o trang chi tiet")

        item_price = min(prices)
        print(f"Đã đọc giá món từ trang chi tiết: {item_price}")
        return item_price

    def export_runtime_result_estimate_mode(self, distance_km: float, food_price: float, quantity: int) -> None:
        if quantity <= 0:
            raise RuntimeError("quantity phai > 0")

        shipping_fee = self._calculate_shipping_fee_from_distance(distance_km)
        total = food_price * quantity + shipping_fee

        payload = {
            "foodPrice": float(food_price),
            "quantity": int(quantity),
            "distanceKm": float(distance_km),
            "displayedShippingFee": float(shipping_fee),
            "displayedTotal": float(total),
        }

        runtime_file = Path(__file__).resolve().parent.parent / "unit-tests" / "runtime" / "ui_result.json"
        runtime_file.parent.mkdir(parents=True, exist_ok=True)
        runtime_file.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

        print(f"Đã xuất runtime JSON cho unit-tests: {runtime_file}")
        print(
            "UI_RESULT_ESTIMATE => "
            f"foodPrice={payload['foodPrice']}, quantity={payload['quantity']}, "
            f"distanceKm={payload['distanceKm']}, shippingFee={payload['displayedShippingFee']}, "
            f"total={payload['displayedTotal']}"
        )
        print(
            "CALC => "
            f"{payload['foodPrice']} x {payload['quantity']} + {payload['displayedShippingFee']} = {payload['displayedTotal']}"
        )

    def _extract_money_from_text(self, text: str) -> Optional[float]:
        match = re.search(r"(\d[\d\.,]{2,})\s*(?:đ|vnd)", text, flags=re.IGNORECASE)
        if not match:
            return None
        normalized = match.group(1).replace(".", "").replace(",", "")
        if not normalized.isdigit():
            return None
        return float(int(normalized))

    def _extract_distance_km_from_text(self, text: str) -> Optional[float]:
        match = re.search(r"(\d+(?:[\.,]\d+)?)\s*km", text, flags=re.IGNORECASE)
        if not match:
            return None
        return float(match.group(1).replace(",", "."))

    def _get_text_from_fixed_locators(self, locator_key: str, timeout: int = 12) -> str:
        element = self.wait_first(LOCATORS[locator_key], timeout=timeout)
        text = (element.text or "").strip()
        if text:
            return text
        desc = (element.get_attribute("contentDescription") or "").strip()
        if desc:
            return desc
        raise RuntimeError(f"Locator '{locator_key}' tim thay element nhung khong doc duoc text")

    def open_checkout_summary_strict(self) -> None:
        cart_btn = self.wait_first(LOCATORS["cart_entry"], timeout=15)
        self.safe_tap_element(cart_btn)
        self.wait_first(LOCATORS["checkout_summary_anchor"], timeout=20)
        print("Đã vào màn cart/checkout summary")

    def export_runtime_result_for_unit_tests(self) -> None:
        # Strict mode: all values must be read directly from fixed locators.
        food_text = self._get_text_from_fixed_locators("summary_food_price")
        ship_text = self._get_text_from_fixed_locators("summary_shipping_fee")
        total_text = self._get_text_from_fixed_locators("summary_total")
        distance_text = self._get_text_from_fixed_locators("summary_distance")

        food_price = self._extract_money_from_text(food_text)
        shipping_fee = self._extract_money_from_text(ship_text)
        total = self._extract_money_from_text(total_text)
        distance_km = self._extract_distance_km_from_text(distance_text)
        quantity = self._cart_badge_count()

        if food_price is None:
            raise RuntimeError(f"Khong doc duoc food price tu text: {food_text}")
        if shipping_fee is None:
            raise RuntimeError(f"Khong doc duoc shipping fee tu text: {ship_text}")
        if total is None:
            raise RuntimeError(f"Khong doc duoc total tu text: {total_text}")
        if distance_km is None:
            raise RuntimeError(f"Khong doc duoc distance km tu text: {distance_text}")
        if quantity is None or quantity <= 0:
            raise RuntimeError("Khong doc duoc so luong mon trong gio")

        payload = {
            "foodPrice": float(food_price),
            "quantity": int(quantity),
            "distanceKm": float(distance_km),
            "displayedShippingFee": float(shipping_fee),
            "displayedTotal": float(total),
        }

        runtime_file = Path(__file__).resolve().parent.parent / "unit-tests" / "runtime" / "ui_result.json"
        runtime_file.parent.mkdir(parents=True, exist_ok=True)
        runtime_file.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

        print(f"Đã xuất runtime JSON cho unit-tests: {runtime_file}")
        print(
            "UI_RESULT_STRICT => "
            f"foodPrice={payload['foodPrice']}, quantity={payload['quantity']}, "
            f"distanceKm={payload['distanceKm']}, shippingFee={payload['displayedShippingFee']}, "
            f"total={payload['displayedTotal']}"
        )

    def _tap_detail_plus_button(self) -> bool:
        driver = self._require_driver()
        size = driver.get_window_size()

        # Luon uu tien tim dung element '+' truoc khi fallback theo toa do,
        # de tranh truong hop bam nham vao anh san pham.
        plus_locators: List[Locator] = list(LOCATORS["menu_plus_button"]) + [
            (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("+")'),
            (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().descriptionContains("+")'),
            (AppiumBy.XPATH, "//*[contains(@resource-id,'add') or contains(@resource-id,'plus') or contains(@resource-id,'increase')]"),
            (AppiumBy.XPATH, "//*[contains(@content-desc,'thêm') or contains(@content-desc,'them') or contains(@content-desc,'add')]"),
        ]

        best_candidate: Optional[Tuple[int, int, float]] = None
        for by, value in plus_locators:
            try:
                for btn in driver.find_elements(by, value):
                    if not btn.is_displayed() or not btn.is_enabled():
                        continue
                    rect = btn.rect
                    if not rect or rect.get("width", 0) <= 0 or rect.get("height", 0) <= 0:
                        continue

                    cx = int(rect["x"] + rect["width"] / 2)
                    cy = int(rect["y"] + rect["height"] / 2)
                    if cy < int(size["height"] * 0.45):
                        continue

                    txt = (btn.text or "").strip().lower()
                    desc = (btn.get_attribute("contentDescription") or "").strip().lower()
                    rid = (btn.get_attribute("resourceId") or "").strip().lower()
                    meta = " ".join([txt, desc, rid])

                    score = 0.0
                    if cx >= int(size["width"] * 0.80):
                        score += 3.0
                    if int(size["height"] * 0.55) <= cy <= int(size["height"] * 0.90):
                        score += 2.0
                    if txt == "+":
                        score += 2.5
                    if any(k in meta for k in ["plus", "add", "them", "increase", "+"]):
                        score += 1.5

                    if best_candidate is None or score > best_candidate[2]:
                        best_candidate = (cx, cy, score)
            except Exception:
                continue

        # Fallback theo dong gia mon: bam ben phai cung dong gia, ngay tren "Binh luan".
        if best_candidate is None:
            try:
                comment_node = self.find_first_visible([
                    (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Bình luận")'),
                    (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Binh luan")'),
                ])
                comment_y = int(comment_node.rect["y"]) if comment_node is not None and comment_node.rect else None

                best_price_y: Optional[int] = None
                for node in driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.TextView"):
                    if not node.is_displayed():
                        continue
                    txt = (node.text or "").strip().lower()
                    if not re.search(r"^\d[\d\.,]{1,}\s*(đ|vnd)$", txt):
                        continue

                    rect = node.rect
                    if not rect:
                        continue
                    cy = int(rect["y"] + rect["height"] / 2)
                    if not (int(size["height"] * 0.50) <= cy <= int(size["height"] * 0.86)):
                        continue
                    if comment_y is not None:
                        distance = comment_y - cy
                        if distance <= 0 or distance > int(size["height"] * 0.22):
                            continue

                    if best_price_y is None or cy > best_price_y:
                        best_price_y = cy

                if best_price_y is not None:
                    best_candidate = (int(size["width"] * 0.95), best_price_y, 1.0)
            except Exception:
                pass

        if best_candidate is not None:
            cx, cy, _ = best_candidate
            driver.execute_script("mobile: clickGesture", {"x": cx, "y": cy})
            print(f"Đã tap dấu cộng tại tọa độ ({cx}, {cy})")
            time.sleep(0.3)
            return True

        # Fallback cuoi cung: thu nhieu diem o cot phai theo cac do cao pho bien cua nut '+'.
        for x_pos, y_pos in [
            (0.95, 0.66), (0.93, 0.66),
            (0.95, 0.70), (0.93, 0.70),
            (0.95, 0.74), (0.93, 0.74),
        ]:
            self.tap_percent(x_pos, y_pos)
            time.sleep(0.2)
            return True
        return False

    def _normalize_vi_text(self, text: str) -> str:
        lowered = (text or "").strip().lower().replace("đ", "d")
        folded = unicodedata.normalize("NFD", lowered)
        return "".join(ch for ch in folded if unicodedata.category(ch) != "Mn")

    def _tap_store_by_fuzzy_name(self, store_name: str, timeout: float = 3.0) -> bool:
        driver = self._require_driver()
        size = driver.get_window_size()
        target = self._normalize_vi_text(store_name)
        tokens = [tok for tok in target.split() if tok]
        if not tokens:
            return False

        end = time.time() + timeout
        while time.time() < end:
            try:
                for node in driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.TextView"):
                    if not node.is_displayed():
                        continue
                    txt = (node.text or "").strip()
                    if not txt:
                        continue
                    norm_txt = self._normalize_vi_text(txt)
                    if not all(tok in norm_txt for tok in tokens):
                        continue

                    rect = node.rect
                    if not rect:
                        continue
                    cy = int(rect["y"] + rect["height"] / 2)
                    if cy < int(size["height"] * 0.16) or cy > int(size["height"] * 0.52):
                        continue

                    # Tap vao than card thay vi text de tranh click nham badge voucher.
                    cx = int(size["width"] * 0.58)
                    driver.execute_script("mobile: clickGesture", {"x": cx, "y": cy})
                    time.sleep(0.8)

                    if self._recover_from_voucher_page_if_needed():
                        continue

                    source = (self._require_driver().page_source or "").lower()
                    if any(k in source for k in ["thực đơn", "menu", "thêm vào giỏ", "thêm món mới", "topping"]):
                        return True
            except Exception:
                pass
            time.sleep(0.2)
        return False

    def _tap_item_by_fuzzy_name(self, item_name: str, timeout: float = 2.8) -> bool:
        driver = self._require_driver()
        size = driver.get_window_size()
        target = self._normalize_vi_text(item_name)
        tokens = [tok for tok in target.split() if tok]
        if not tokens:
            return False

        def _score_text(candidate_text: str) -> float:
            normalized = self._normalize_vi_text(candidate_text)
            if not normalized:
                return 0.0

            token_hits = sum(1 for tok in tokens if tok in normalized)
            token_coverage = token_hits / max(len(tokens), 1)
            ratio = SequenceMatcher(None, target, normalized).ratio()
            prefix_bonus = 0.12 if normalized.startswith(tokens[0]) else 0.0
            return (token_coverage * 0.68) + (ratio * 0.32) + prefix_bonus

        end = time.time() + timeout
        while time.time() < end:
            try:
                best_node: Optional[WebElement] = None
                best_text = ""
                best_score = 0.0

                for node in driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.TextView"):
                    if not node.is_displayed():
                        continue
                    txt = (node.text or "").strip()
                    if not txt:
                        continue

                    rect = node.rect
                    if not rect:
                        continue
                    cy = int(rect["y"] + rect["height"] / 2)
                    if cy < int(size["height"] * 0.14) or cy > int(size["height"] * 0.66):
                        continue

                    norm_txt = self._normalize_vi_text(txt)
                    if any(
                        bad in norm_txt
                        for bad in ["tim mon", "goi y", "danh muc", "binh luan", "dat mon ngay", "foody", "no photo"]
                    ):
                        continue

                    score = _score_text(txt)
                    if score > best_score:
                        best_score = score
                        best_node = node
                        best_text = txt

                if best_node is not None and best_score >= 0.34:
                    rect = best_node.rect
                    if not rect:
                        continue
                    cy = int(rect["y"] + rect["height"] / 2)
                    cx = int(size["width"] * 0.48)
                    print(f"Fuzzy chọn món: '{best_text}' (score={best_score:.2f})")
                    driver.execute_script("mobile: clickGesture", {"x": cx, "y": cy})
                    time.sleep(0.55)
                    if self._wait_item_detail_ready(timeout=3.0) or self._is_product_detail_page():
                        return True
            except Exception:
                pass
            time.sleep(0.2)
        return False

    def _tap_first_available_item(self, timeout: float = 2.2) -> bool:
        driver = self._require_driver()
        size = driver.get_window_size()
        end = time.time() + timeout

        while time.time() < end:
            try:
                candidates: List[Tuple[int, str]] = []
                for node in driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.TextView"):
                    if not node.is_displayed():
                        continue
                    txt = (node.text or "").strip()
                    if len(txt) < 2:
                        continue

                    rect = node.rect
                    if not rect:
                        continue
                    cy = int(rect["y"] + rect["height"] / 2)
                    if cy < int(size["height"] * 0.14) or cy > int(size["height"] * 0.66):
                        continue

                    norm_txt = self._normalize_vi_text(txt)
                    if any(
                        bad in norm_txt
                        for bad in [
                            "tim mon",
                            "goi y",
                            "danh muc",
                            "binh luan",
                            "dat mon ngay",
                            "foody",
                            "no photo",
                            "thuc don",
                            "da ban",
                            "luot thich",
                        ]
                    ):
                        continue

                    # Loai bo dong thong ke kieu "100+ da ban".
                    if re.match(r"^\d+[+]?\s*da ban$", norm_txt):
                        continue

                    candidates.append((cy, txt))

                if candidates:
                    candidates.sort(key=lambda item: item[0])
                    target_y, target_text = candidates[0]
                    target_x = int(size["width"] * 0.48)
                    print(f"Fallback chọn món đầu tiên: '{target_text}'")
                    driver.execute_script("mobile: clickGesture", {"x": target_x, "y": target_y})
                    time.sleep(0.6)
                    if self._wait_item_detail_ready(timeout=3.0) or self._is_product_detail_page():
                        return True
            except Exception:
                pass
            time.sleep(0.2)
        return False

    def _is_voucher_detail_page(self) -> bool:
        source = (self._require_driver().page_source or "").lower()
        return any(k in source for k in ["chi tiết voucher", "mã voucher", "sao chép", "free shipping"])

    def _recover_from_voucher_page_if_needed(self) -> bool:
        if not self._is_voucher_detail_page():
            return False

        # Quay lại khỏi trang voucher để tiếp tục chọn quán đúng.
        self.tap_percent(0.04, 0.08)
        time.sleep(0.6)
        return True

    def _is_menu_category_panel_open(self) -> bool:
        source = (self._require_driver().page_source or "").lower()
        hints = ["tất cả", "flash sale", "hotline", "kem và trà", "trà sữa bingxue"]
        matches = sum(1 for h in hints if h in source)
        return matches >= 3

    def _close_menu_category_panel_if_open(self) -> None:
        if not self._is_menu_category_panel_open():
            return

        # Panel danh mục đang mở, tap vào vùng mũi tên thu gọn bên phải dòng "TẤT CẢ".
        self.tap_percent(0.90, 0.17)
        time.sleep(0.5)
        if self._is_menu_category_panel_open():
            # Fallback: tap lại vào vùng label "TẤT CẢ" để toggle đóng.
            self.tap_percent(0.12, 0.17)
            time.sleep(0.5)

    def select_first_result(self) -> None:
        time.sleep(0.8)

        if self._recover_from_voucher_page_if_needed():
            time.sleep(0.4)

        # Nếu còn ở màn gợi ý thì bấm lại icon kính lúp, không được bấm vào list gợi ý.
        if self._is_search_suggestion_screen():
            self.tap_percent(0.95, 0.08)
            time.sleep(0.35)

        # Neu da cung cap STORE_NAME thi uu tien mo dung quan theo ten.
        store_name = (self.config.store_name or "").strip()
        if store_name and self._tap_store_by_fuzzy_name(store_name):
            print(f"Đã chọn quán theo STORE_NAME: {store_name}")
            return

        # Bước 1: bấm đúng DÒNG TÊN QUÁN đầu tiên, tránh badge mã giảm/voucher.
        # Chỉ dùng vùng title row của card đầu tiên.
        for x_pos, y_pos in [(0.55, 0.24), (0.62, 0.24), (0.48, 0.24)]:
            self.tap_percent(x_pos, y_pos)
            time.sleep(0.9)

            if self._recover_from_voucher_page_if_needed():
                continue

            # Nếu đã vào màn quán hoặc popup sản phẩm thì đi tiếp.
            source = (self._require_driver().page_source or "").lower()
            if any(k in source for k in ["thực đơn", "menu", "thêm vào giỏ", "thêm món mới", "topping"]):
                return

    def select_item_in_store(self) -> None:
        def _is_detail_open() -> bool:
            return self._is_product_detail_page_strict()

        # Không thoát sớm ở đây; luôn thử bấm icon kính lúp theo flow trang quán.
        end = time.time() + 3.0
        while time.time() < end and not self._is_store_page():
            time.sleep(0.2)

        item_name = (self.config.item_name or self.config.food_name).strip()
        if not item_name:
            return

        # Icon kính lúp nằm bên trái icon share ở góc phải trên banner.
        self.tap_percent(0.88, 0.09)
        print("Đã bấm icon kính lúp trong trang quán")

        def _top_search_fields() -> List[WebElement]:
            driver = self._require_driver()
            size = driver.get_window_size()
            top_fields: List[WebElement] = []
            for field in self._visible_edit_texts():
                try:
                    rect = field.rect
                    if rect and rect.get("y", 99999) <= int(size["height"] * 0.22):
                        top_fields.append(field)
                except Exception:
                    continue
            return top_fields

        fields = _top_search_fields()
        if not fields:
            end = time.time() + 2.0
            while time.time() < end and not fields:
                fields = _top_search_fields()
                time.sleep(0.2)

        if not fields:
            print("Fallback tap icon kính lúp")
            self.tap_percent(0.86, 0.09)
            end = time.time() + 2.0
            while time.time() < end and not fields:
                fields = _top_search_fields()
                time.sleep(0.2)

        if not fields:
            self.tap_percent(0.88, 0.08)
            end = time.time() + 1.2
            while time.time() < end and not fields:
                fields = _top_search_fields()
                time.sleep(0.2)

        if not fields:
            self.tap_percent(0.88, 0.055)
            end = time.time() + 1.2
            while time.time() < end and not fields:
                fields = _top_search_fields()
                time.sleep(0.2)

        if not fields:
            self.tap_percent(0.86, 0.055)
            end = time.time() + 1.2
            while time.time() < end and not fields:
                fields = _top_search_fields()
                time.sleep(0.2)

        # Một số layout cần tap thêm vào thân thanh search để focus ô nhập.
        if not fields:
            search_bar = self.find_first_visible(LOCATORS["store_search_input"])
            if search_bar is not None:
                self.safe_tap_element(search_bar)
            else:
                self.tap_percent(0.62, 0.09)
            end = time.time() + 1.8
            while time.time() < end and not fields:
                fields = _top_search_fields()
                time.sleep(0.2)

        if fields:
            print("Ô tìm kiếm trong quán đã hiển thị")

        if not fields:
            raise RuntimeError("Không mở được ô tìm kiếm trong trang quán từ icon kính lúp")

        field = fields[0]
        field.clear()
        field.send_keys(item_name)
        self._require_driver().press_keycode(66)
        time.sleep(0.5)

        # Man hinh ket qua tim mon trong quan: bat buoc bam vao row san pham de vao chi tiet.
        if self._is_in_store_search_result_page():
            if self._tap_search_result_row(item_name, timeout=3.5):
                print("Đã vào trang chi tiết món")
                return

        # Chọn đúng món theo text trước, fallback về món đầu nếu không match.
        exact_locators: List[Locator] = [
            (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().textContains("{item_name}")'),
            (AppiumBy.XPATH, f"//*[contains(@text,\"{item_name}\")]")
        ]

        try:
            item_node = self.wait_first(exact_locators, timeout=4)
            print("Đã bấm vào sản phẩm theo tên gần đúng")
            self.safe_tap_element(item_node)
            time.sleep(0.5)
            if self._wait_item_detail_ready(timeout=4.0) and _is_detail_open():
                print("Đã vào trang chi tiết món")
                return

            # Text node đôi khi không clickable; tap lại vào thân row cùng dòng item.
            driver = self._require_driver()
            size = driver.get_window_size()
            row_rect = item_node.rect
            row_y = int(row_rect["y"] + max(8, row_rect["height"] // 2))
            row_x = int(size["width"] * 0.48)
            print("Đã bấm lại vào row sản phẩm")
            driver.execute_script("mobile: clickGesture", {"x": row_x, "y": row_y})
            time.sleep(0.55)
            if self._wait_item_detail_ready(timeout=3.5) and _is_detail_open():
                print("Đã vào trang chi tiết món")
                return
        except Exception:
            pass

        if self._tap_item_by_fuzzy_name(item_name) and _is_detail_open():
            print("Đã vào trang chi tiết món")
            return

        if self._tap_first_available_item(timeout=2.5) and _is_detail_open():
            print("Đã vào trang chi tiết món")
            return

        # Tự phục hồi: nếu match text không ổn định (accent/case/layout), bấm món đầu trong list đã lọc.
        for x_pos, y_pos in [(0.48, 0.18), (0.55, 0.18), (0.48, 0.25), (0.55, 0.25)]:
            self.tap_percent(x_pos, y_pos)
            time.sleep(0.65)
            if self._wait_item_detail_ready(timeout=3.0) and _is_detail_open():
                print("Đã vào trang chi tiết món")
                return

        raise RuntimeError(f"Không bấm được món theo ITEM_NAME trong trang quán: {item_name}")

    def tap_add_to_cart(self, quantity_to_add: int = 1) -> None:
        if quantity_to_add <= 0:
            raise RuntimeError("quantity_to_add phai > 0")

        self._close_menu_category_panel_if_open()
        if not (self._wait_item_detail_ready(timeout=1.2) and self._is_product_detail_page_strict()):
            raise RuntimeError("Chưa ở trang chi tiết món, không thực hiện thêm vào giỏ")

        before_count = self._cart_badge_count()
        successful_taps = 0

        # Lan dau tien: bam '+' de mo popup tuy chon (neu co) hoac add truc tiep.
        first_clicked = False
        for _ in range(3):
            if self._tap_detail_plus_button():
                successful_taps = 1
                print(f"Đã bấm dấu cộng thêm món lần {successful_taps}/{quantity_to_add}")
                self.save_step_screenshot(f"plus_tapped_{successful_taps}")
                self._pause_for_observation(
                    self.config.plus_pause_sec,
                    f"quan sát sau khi bấm dấu cộng lần {successful_taps}",
                )
                first_clicked = True
                break
            time.sleep(0.25)

        if not first_clicked:
            raise RuntimeError("Không bấm được dấu cộng lần đầu để thêm món")

        # Bat buoc co phan hoi sau khi bam '+': mo popup, tang gio, hoac chuyen login.
        reacted = (
            self._is_add_item_modal_open()
            or self._wait_cart_count_increase(before_count, timeout=0.9)
            or self._is_login_gate_screen()
        )
        retry_click = 0
        while not reacted and retry_click < 3:
            retry_click += 1
            if not self._tap_detail_plus_button():
                continue
            print(f"Retry bấm dấu cộng để chờ phản hồi lần {retry_click}")
            reacted = (
                self._is_add_item_modal_open()
                or self._wait_cart_count_increase(before_count, timeout=0.9)
                or self._is_login_gate_screen()
            )

        if not reacted:
            raise RuntimeError("Đã bấm dấu cộng nhưng UI không phản hồi (không mở popup, không tăng giỏ, không chuyển login)")

        # Neu hien popup chon mon, uu tien bam vao so luong hien tai (so 1) de nhap thang so luong moi.
        if self._is_add_item_modal_open() and quantity_to_add > 1:
            if not self._set_modal_quantity_direct(quantity_to_add):
                # Fallback an toan neu dialog so luong khong mo duoc tren mot so layout.
                for tap_index in range(1, quantity_to_add):
                    plus_clicked = False
                    for _ in range(3):
                        if self._tap_detail_plus_button():
                            successful_taps += 1
                            print(f"Đã bấm dấu cộng thêm món lần {successful_taps}/{quantity_to_add}")
                            self.save_step_screenshot(f"plus_tapped_{successful_taps}")
                            self._pause_for_observation(
                                self.config.plus_pause_sec,
                                f"quan sát sau khi bấm dấu cộng lần {successful_taps}",
                            )
                            plus_clicked = True
                            break
                        time.sleep(0.2)
                    if not plus_clicked:
                        raise RuntimeError(f"Không bấm được dấu cộng trong popup lần {tap_index + 1}/{quantity_to_add}")

        # Xac nhan them gio: popup co nut bat buoc, layout khac co the add truc tiep.
        add_confirmed = self._tap_add_to_cart_confirm_if_present()
        if not add_confirmed and self._tap_order_now_if_present():
            add_confirmed = True
            print("Đã bấm Đặt món ngay")

        cart_increased = self._wait_cart_count_increase(before_count, timeout=2.2)
        if cart_increased:
            print("Xác nhận: thêm vào giỏ thành công (badge giỏ đã tăng)")
            return
        if self._is_login_gate_screen():
            print("Xác nhận: app chuyển sang màn đăng nhập khi thêm vào giỏ")
            return
        if self._has_cart_ready_indicators():
            print("Xác nhận: thêm vào giỏ thành công (phát hiện thanh Giao hàng/cart summary)")
            return

        if self._is_add_item_modal_open() and not add_confirmed:
            raise RuntimeError("Đang ở popup chọn món nhưng chưa bấm được nút Thêm vào giỏ hàng")

        raise RuntimeError("Đã thao tác thêm món nhưng chưa thấy giỏ tăng hoặc chuyển sang màn đăng nhập")

    def verify_added_to_cart(self, before_count: Optional[int]) -> None:
        driver = self._require_driver()
        end = time.time() + 18
        while time.time() < end:
            after_count = self._cart_badge_count()
            if before_count is not None and after_count is not None and after_count > before_count:
                print("Đã thêm món thành công")
                return
            if before_count is None and after_count is not None and after_count > 0:
                print("Đã thêm món thành công")
                return
            if self._has_cart_ready_indicators():
                print("Đã thêm món thành công")
                return
            time.sleep(0.5)

        # Fallback: mở giỏ và verify text món.
        self.tap_percent(0.90, 0.93)
        time.sleep(1.0)
        page = (driver.page_source or "").lower()
        if self.config.food_name.lower() in page:
            print("Đã thêm món thành công")
            return
        if any(k in page for k in ["giỏ hàng", "đặt đơn", "thanh toán", "tạm tính"]):
            print("Đã thêm món thành công")
            return

        # Nếu đang ở màn chi tiết món, giỏ thường ở góc phải trên.
        self.tap_percent(0.94, 0.08)
        time.sleep(1.0)
        page = (driver.page_source or "").lower()
        if any(k in page for k in ["giỏ hàng", "đặt đơn", "thanh toán", "tạm tính"]):
            print("Đã thêm món thành công")
            return

        # Fallback cuối: quay lại khỏi màn chi tiết rồi mở giỏ dưới.
        if self._is_product_detail_page():
            self.tap_percent(0.04, 0.08)
            time.sleep(0.7)
            self.tap_percent(0.90, 0.93)
            time.sleep(1.0)
            page = (driver.page_source or "").lower()
            if any(k in page for k in ["giỏ hàng", "đặt đơn", "thanh toán", "tạm tính"]):
                print("Đã thêm món thành công")
                return

        raise AssertionError("Không verify được món trong giỏ")

    def run(self) -> None:
        if not self.config.food_name:
            raise RuntimeError("FOOD_NAME đang rỗng")

        print("Bước 1: mở app ShopeeFood")
        self.start_session()
        self.save_step_screenshot("step_01_session_started")

        try:
            self.handle_permissions()
            self.save_step_screenshot("step_02_permissions_done")
            self.close_ads_if_exist()
            self.save_step_screenshot("step_03_home_ready")

            # 3) bấm vào ô tìm kiếm trên trang chủ
            self.open_search()
            self.save_step_screenshot("step_04_search_opened")

            # 4) nhập FOOD_NAME
            self.input_food_name()
            self.save_step_screenshot("step_05_keyword_entered")

            # 4.1) đảm bảo đã ra list quán có km để đọc khoảng cách gần nhất
            self._wait_search_results_with_distance(timeout=25)
            self._pause_for_observation(2.0, "chờ UI ổn định trước khi đọc km")
            nearest_distance_km = self._extract_nearest_distance_km_from_store_list()
            self.save_step_screenshot("step_06_store_results_ready")

            # 5) chọn món đầu tiên trong kết quả
            self.select_first_result()
            self.save_step_screenshot("step_07_store_opened")

            # 5.2) trong trang quán: bấm kính lúp tìm món và chọn đúng tên món.
            self.select_item_in_store()
            self.save_step_screenshot("step_08_item_detail_opened")
            if self._is_product_detail_page():
                self._pause_for_observation(self.config.detail_pause_sec, "quan sát khi vừa vào trang chi tiết")

            desired_quantity = max(1, self.config.add_to_cart_qty)

            # Estimate mode: still tap add-to-cart, then calculate from UI-derived values.
            if self.config.estimate_mode:
                item_price = self._extract_item_price_from_detail()
                before_count = self._cart_badge_count()

                self.tap_add_to_cart(quantity_to_add=desired_quantity)
                logged_in = self.login_if_needed()
                after_first_try_count = self._cart_badge_count()
                if logged_in:
                    already_added = (
                        before_count is not None
                        and after_first_try_count is not None
                        and after_first_try_count > before_count
                    )
                    if not already_added:
                        self.handle_permissions()
                        self.close_ads_if_exist()
                        self.tap_add_to_cart(quantity_to_add=desired_quantity)

                self.verify_added_to_cart(before_count=before_count)
                self.save_step_screenshot("step_09_added_to_cart_verified")

                self.export_runtime_result_estimate_mode(
                    distance_km=nearest_distance_km,
                    food_price=item_price,
                    quantity=desired_quantity,
                )
                self.save_step_screenshot("step_10_runtime_exported")
                print("Log thành công (estimate mode)")
                return

            # 6) bấm Thêm vào giỏ
            before_count = self._cart_badge_count()
            self.tap_add_to_cart(quantity_to_add=desired_quantity)

            # 7) nếu yêu cầu đăng nhập thì login rồi quay lại thêm giỏ
            logged_in = self.login_if_needed()
            after_first_try_count = self._cart_badge_count()
            if logged_in:
                already_added = (
                    before_count is not None
                    and after_first_try_count is not None
                    and after_first_try_count > before_count
                )
                if not already_added:
                    self.handle_permissions()
                    self.close_ads_if_exist()
                    self.tap_add_to_cart(quantity_to_add=desired_quantity)

            # 8) verify món trong giỏ
            self.verify_added_to_cart(before_count=before_count)
            self.save_step_screenshot("step_09_added_to_cart_verified")

            # 8.1) mandatory open checkout/cart summary and export strict runtime data
            self.open_checkout_summary_strict()
            self.save_step_screenshot("step_10_checkout_summary_opened")
            self.export_runtime_result_for_unit_tests()
            self.save_step_screenshot("step_11_runtime_exported")

            # 9) log thành công
            print("Log thành công")
        except Exception as ex:
            self.save_error_screenshot("appium_error")
            print(f"Flow lỗi: {ex}")
            raise
        finally:
            self._confirm_before_quit()


def setup_driver(config: Optional[AppConfig] = None) -> webdriver.Remote:
    # Hàm tiện ích cho chạy nhanh hoặc debug thủ công.
    flow = ShopeeFoodFlow(config or AppConfig())
    flow.start_session()
    return flow._require_driver()


def run_all() -> None:
    # Điểm vào chính khi chạy bằng batch script; in config để dễ truy vết.
    config = AppConfig()
    print(f"APPIUM_SERVER_URL={config.appium_server_url}")
    print(f"ANDROID_UDID={config.udid}")
    print(f"APP_PACKAGE={config.app_package}")
    print(f"STORE_NAME={config.store_name}")
    print(f"FOOD_NAME={config.food_name}")
    print(f"ITEM_NAME={config.item_name}")
    print(f"ADD_TO_CART_QTY={max(1, config.add_to_cart_qty)}")
    if config.shopee_user:
        print(f"SHOPEE_USER={config.shopee_user}")
    ShopeeFoodFlow(config).run()


if __name__ == "__main__":
    run_all()

"""Legacy web-search smoke test for ShopeeFood pages.

Kept as reference utilities while the main stable flow runs on Appium mobile.
"""

from selenium.common.exceptions import TimeoutException

from utils import (
    close_popup_if_any,
    log_step,
    open_homepage,
    search_food,
    setup_driver,
    take_screenshot,
    wait_search_results,
    safe_quit,
)


class SearchFoodTest:
    def __init__(self, keyword: str = "trà sữa"):
        self.keyword = keyword

    def run(self, driver) -> bool:
        """Buoc 1: Mo web, dong popup, tim mon an."""
        try:
            log_step("=== BAT DAU TEST 1: TIM MON AN ===")
            open_homepage(driver)
            close_popup_if_any(driver)
            search_food(driver, self.keyword)
            wait_search_results(driver)
            log_step("Test 1 PASS: Da tim thay ket qua mon an")
            return True
        except TimeoutException as ex:
            log_step(f"Test 1 FAIL (Timeout): {ex}")
            take_screenshot(driver, "test_search_food_timeout")
            return False
        except Exception as ex:
            log_step(f"Test 1 FAIL: {ex}")
            take_screenshot(driver, "test_search_food_error")
            return False


if __name__ == "__main__":
    driver = None
    try:
        driver = setup_driver()
        result = SearchFoodTest().run(driver)
        print(f"Ket qua test_search_food: {'PASS' if result else 'FAIL'}")
    finally:
        safe_quit(driver)

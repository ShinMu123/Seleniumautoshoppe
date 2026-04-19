"""Legacy web checkout smoke test.

Useful for structure/reference only; full mobile order flow is automated in
`main.py` with Appium.
"""

from utils import (
    close_popup_if_any,
    go_to_checkout,
    log_step,
    open_cart,
    safe_quit,
    setup_driver,
    take_screenshot,
    verify_checkout_page,
)
from test_add_to_cart import AddToCartTest


class PlaceOrderTest:
    def __init__(self, keyword: str = "trà sữa"):
        self.keyword = keyword

    def run(self, driver, pre_added: bool = False) -> bool:
        """Buoc 3: Mo gio, nhan dat hang, verify qua checkout."""
        try:
            log_step("=== BAT DAU TEST 3: TIEN HANH DAT HANG ===")

            if not pre_added:
                if not AddToCartTest(self.keyword).run(driver, pre_searched=False):
                    raise Exception("Khong the dat hang vi chua them mon vao gio")

            close_popup_if_any(driver)
            open_cart(driver)
            close_popup_if_any(driver)
            go_to_checkout(driver)

            if not verify_checkout_page(driver):
                raise AssertionError("Khong chuyen duoc sang trang checkout")

            log_step("Test 3 PASS: Da chuyen sang man checkout")
            return True
        except Exception as ex:
            log_step(f"Test 3 FAIL: {ex}")
            take_screenshot(driver, "test_place_order_error")
            return False


if __name__ == "__main__":
    driver = None
    try:
        driver = setup_driver()
        result = PlaceOrderTest().run(driver, pre_added=False)
        print(f"Ket qua test_place_order: {'PASS' if result else 'FAIL'}")
    finally:
        safe_quit(driver)

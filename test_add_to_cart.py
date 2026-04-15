from utils import (
    add_first_food_to_cart,
    close_popup_if_any,
    get_cart_count,
    log_step,
    open_first_shop,
    safe_quit,
    setup_driver,
    take_screenshot,
)
from test_search_food import SearchFoodTest


class AddToCartTest:
    def __init__(self, keyword: str = "trà sữa"):
        self.keyword = keyword

    def run(self, driver, pre_searched: bool = False) -> bool:
        """Buoc 2: Chon quan dau, them mon dau, verify gio tang."""
        try:
            log_step("=== BAT DAU TEST 2: THEM MON VAO GIO ===")

            if not pre_searched:
                if not SearchFoodTest(self.keyword).run(driver):
                    raise Exception("Khong the tim mon an truoc khi them vao gio")

            close_popup_if_any(driver)
            open_first_shop(driver)
            close_popup_if_any(driver)

            before_count = get_cart_count(driver)
            log_step(f"So luong gio hang truoc khi them: {before_count}")

            add_first_food_to_cart(driver)

            after_count = get_cart_count(driver)
            log_step(f"So luong gio hang sau khi them: {after_count}")

            if after_count <= before_count:
                raise AssertionError("Gio hang khong tang so luong sau khi them mon")

            log_step("Test 2 PASS: Them vao gio thanh cong")
            return True
        except Exception as ex:
            log_step(f"Test 2 FAIL: {ex}")
            take_screenshot(driver, "test_add_to_cart_error")
            return False


if __name__ == "__main__":
    driver = None
    try:
        driver = setup_driver()
        result = AddToCartTest().run(driver, pre_searched=False)
        print(f"Ket qua test_add_to_cart: {'PASS' if result else 'FAIL'}")
    finally:
        safe_quit(driver)

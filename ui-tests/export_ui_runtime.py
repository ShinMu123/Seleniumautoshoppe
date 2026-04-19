"""Xuất số liệu UI ra runtime JSON cho bài test cầu nối .NET.

Script này đọc giá trị từ biến môi trường và ghi payload đã chuẩn hóa
để NUnit dùng cho phần assert.
"""

import json
import os
from pathlib import Path


def calculate_shipping_fee(distance_km: float) -> float:
    # Đồng bộ công thức phí ship với OrderCalculator.cs để UI và unit dùng cùng luật.
    if distance_km < 0:
        raise ValueError("distance_km must be non-negative")

    # Luật nghiệp vụ: luôn làm tròn lên km trước khi áp bậc phí.
    rounded_distance = int(distance_km) if distance_km.is_integer() else int(distance_km) + 1

    if rounded_distance <= 3:
        return 17000.0
    if rounded_distance <= 5:
        return 17000.0 + (rounded_distance - 3) * 5500.0
    if rounded_distance <= 10:
        return 28500.0 + (rounded_distance - 6) * 6000.0
    return 57000.0 + (rounded_distance - 11) * 5500.0


def read_float_env(key: str, default: float | None = None) -> float:
    # Hàm đọc env dùng chung, có default để tránh lặp logic validate.
    value = os.environ.get(key)
    if value is None or not value.strip():
        if default is None:
            raise ValueError(f"Missing required environment variable: {key}")
        return default
    return float(value.strip())


def read_int_env(key: str, default: int | None = None) -> int:
    # Cùng cơ chế với read_float_env nhưng parse int cho các trường số lượng.
    value = os.environ.get(key)
    if value is None or not value.strip():
        if default is None:
            raise ValueError(f"Missing required environment variable: {key}")
        return default
    return int(value.strip())


def main() -> None:
    # Input bắt buộc được cung cấp từ UI flow hoặc script export.
    food_price = read_float_env("UI_RESULT_FOOD_PRICE")
    quantity = read_int_env("UI_RESULT_QUANTITY", default=1)
    distance_km = read_float_env("UI_RESULT_DISTANCE_KM")

    shipping_fee_raw = os.environ.get("UI_RESULT_SHIPPING_FEE", "").strip()
    total_raw = os.environ.get("UI_RESULT_TOTAL", "").strip()

    # Input tùy chọn: nếu thiếu thì tự tính theo công thức chuẩn.
    shipping_fee = float(shipping_fee_raw) if shipping_fee_raw else calculate_shipping_fee(distance_km)
    total = float(total_raw) if total_raw else (food_price * quantity + shipping_fee)

    output = {
        "foodPrice": round(food_price, 2),
        "quantity": quantity,
        "distanceKm": round(distance_km, 2),
        "displayedShippingFee": round(shipping_fee, 2),
        "displayedTotal": round(total, 2),
    }

    # Đây là file cầu nối mà UiToUnitBridgeTests.cs sẽ đọc.
    target_file = Path(__file__).resolve().parent.parent / "unit-tests" / "runtime" / "ui_result.json"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text(json.dumps(output, ensure_ascii=True, indent=2), encoding="utf-8")

    print(f"Da luu runtime JSON: {target_file}")
    print(json.dumps(output, ensure_ascii=True))


if __name__ == "__main__":
    main()

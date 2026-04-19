"""Tiện ích CLI để đẩy số liệu UI vào runtime JSON của unit-tests.

Dùng script này khi bạn lấy số liệu thủ công hoặc từ runner khác.
"""

import argparse
import json
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    # Đặt tên tham số rõ ràng để dễ đọc khi chụp báo cáo hoặc chạy lại bằng terminal.
    parser = argparse.ArgumentParser(
        description="Xuat so lieu UI test sang runtime JSON de NUnit kiem tra."
    )
    parser.add_argument("--food-price", type=float, required=True)
    parser.add_argument("--quantity", type=int, required=True)
    parser.add_argument("--distance-km", type=float, required=True)
    parser.add_argument("--shipping-fee", type=float, required=True)
    parser.add_argument("--total", type=float, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()

    # Chuẩn hóa số trước khi ghi JSON để giảm sai số lẻ khi assert.
    output = {
        "foodPrice": round(args.food_price, 2),
        "quantity": args.quantity,
        "distanceKm": round(args.distance_km, 2),
        "displayedShippingFee": round(args.shipping_fee, 2),
        "displayedTotal": round(args.total, 2),
    }

    # Đường dẫn runtime dùng chung cho test cầu nối .NET.
    target_file = Path(__file__).resolve().parent.parent / "unit-tests" / "runtime" / "ui_result.json"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text(json.dumps(output, ensure_ascii=True, indent=2), encoding="utf-8")

    print(f"Da xuat ket qua UI vao: {target_file}")


if __name__ == "__main__":
    main()

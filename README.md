# FoodOrderSelenium - Hướng dẫn chạy Appium ShopeeFood

## 1) Mục đích
Script tự động hóa ShopeeFood trên Android Emulator:
- Mở app ShopeeFood
- Tìm quán/món theo từ khóa
- Click vào row kết quả để vào trang chi tiết món
- Bấm dấu cộng để tăng số lượng
- Nếu chưa đăng nhập: bấm "Đăng nhập bằng mật khẩu", nhập tài khoản/mật khẩu từ .env
- Xác nhận đã thêm vào giỏ

## 2) Yêu cầu môi trường
- Windows
- Python 3
- Android Emulator hoặc thiết bị thật (adb nhìn thấy)
- Appium server
- App ShopeeFood với package: com.deliverynow (hoặc đổi trong .env)

## 3) Cấu hình .env
Chỉnh file .env trong thư mục project:

- STORE_NAME: tên cửa hàng (có thể để trống)
- FOOD_NAME: từ khóa tìm trên trang chủ
- ITEM_NAME: tên món cần chọn trong quán
- SHOPEE_USER: tên đăng nhập (email/sđt)
- SHOPEE_PASS: mật khẩu

- APPIUM_SERVER_URL: mặc định http://127.0.0.1:4723
- ANDROID_UDID: mặc định emulator-5554
- SHOPEEFOOD_APP_PACKAGE: mặc định com.deliverynow

- DETAIL_PAUSE_SEC: số giây dừng khi vừa vào trang chi tiết
- PLUS_PAUSE_SEC: số giây dừng sau khi bấm dấu cộng
- AUTO_QUIT:
  - 0: giữ app mở, đợi Enter trong terminal mới đóng
  - 1: tự động đóng app khi kết thúc

Lưu ý bảo mật:
- Không chia sẻ .env vì có chứa tài khoản/mật khẩu.

## 4) Cách chạy
### Cách nhanh (khuyến nghị)
Chạy file batch:

```bat
run_all.bat
```

Batch sẽ tự động:
- Tạo virtualenv nếu chưa có
- Cài dependencies
- Kiểm tra/auto mở Appium
- Chạy main.py

### Chạy bằng PowerShell trong thư mục project

```powershell
.\run_all.bat
```

### Chạy 1 lần và tự động đóng app

```powershell
$env:AUTO_QUIT='1'; .\run_all.bat
```

## 5) Code đang làm gì (tóm tắt flow)
File chính: main.py

1. Khởi tạo Appium session
2. Xử lý permission/popup
3. Mở ô tìm kiếm và tìm FOOD_NAME
4. Mở quán
5. Trong quán, tìm ITEM_NAME
6. Nếu đang ở màn kết quả tìm món trong quán:
   - Click vào thân row sản phẩm (không bấm dấu +)
   - Bắt buộc vào trang chi tiết món mới cho đi tiếp
7. Ở trang chi tiết:
   - Bấm dấu cộng theo tọa độ động (adaptive theo layout)
   - Nếu cần, bấm "Thêm vào giỏ hàng"
8. Nếu bị chặn login:
   - Bấm "Đăng nhập bằng mật khẩu"
   - Điền SHOPEE_USER/SHOPEE_PASS
   - Bấm "Đăng nhập"
9. Verify đã thêm món vào giỏ

## 6) Log cần nhìn để biết đã đúng flow
- "Đã bấm row kết quả tìm kiếm tại (...)"
- "Đã vào trang chi tiết món"
- "Đã bấm dấu cộng thêm món"
- "Đăng nhập thành công" (nếu có login)
- "Đã thêm món thành công"

## 7) Lỗi thường gặp
### Không tìm thấy adb
- Cài Android SDK Platform-Tools
- Thêm adb vào PATH hoặc set ADB_PATH

### Không kết nối được Appium
- Mở Appium server
- Kiểm tra APPIUM_SERVER_URL

### Không tìm được món
- Thử đổi ITEM_NAME ngắn gọn hơn
- Kiểm tra cửa hàng có món tương ứng

### Không vào được trang chi tiết
- Script đã ép click row kết quả tìm kiếm trước
- Tăng DETAIL_PAUSE_SEC để quan sát

## 8) Dependencies
Trong requirements.txt:
- Appium-Python-Client>=4.0.0
- selenium>=4.20.0

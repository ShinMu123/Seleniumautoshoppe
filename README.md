# FoodOrderSelenium - Hướng Dẫn Tổng Cho Bài Tập

## Vì sao không dùng Selenium mà dùng Appium?

Trong bài này, nhóm kiểm thử luồng đặt món trên ứng dụng ShopeeFood chạy trên Android Emulator, không phải website chạy trên trình duyệt. Vì vậy, Appium là lựa chọn phù hợp hơn Selenium cho phần UI automation.

Lý do cụ thể:
1. Selenium chủ yếu tự động hóa trình duyệt web (Chrome, Edge, Firefox), không điều khiển tốt giao diện native app Android/iOS.
2. Appium được thiết kế cho mobile automation, hỗ trợ thao tác trực tiếp trên app như bấm nút native, nhập liệu, vuốt, xử lý popup quyền hệ thống.
3. Khi thử trên ShopeeFood bản web, thao tác bấm Thêm vào giỏ hàng không ổn định trong môi trường tự động hóa (dễ bị chặn bởi popup, lớp phủ giao diện hoặc thay đổi DOM), nên khó đảm bảo chạy lặp lại tin cậy.
4. Kịch bản bài tập cần kiểm thử luồng thực tế trên app (mở app, tìm món, thêm giỏ, đăng nhập), nên cần driver mobile (UiAutomator2) thay vì web driver của Selenium.
5. Cách làm này giúp kết quả sát với trải nghiệm người dùng trên điện thoại hơn so với kiểm thử web giả lập.

Tóm lại: Selenium phù hợp cho web, còn Appium phù hợp cho mobile app. Vì mục tiêu của bài là kiểm thử ứng dụng Android, nên chọn Appium là đúng phạm vi kỹ thuật.
“Trong quá trình kiểm thử website ShopeeFood, ở bước Thêm vào giỏ hàng hệ thống không cho đặt trực tiếp trên web mà chuyển sang cơ chế App-only (hiển thị QR/tải app). Vì vậy Selenium không thể hoàn tất luồng Thêm giỏ và Đặt hàng trên web, không phải do lỗi script mà do ràng buộc nghiệp vụ của nền tảng.
Nhóm đã xử lý bằng cách:

Vẫn dùng Selenium cho phần web có thể kiểm thử (tìm món, điều hướng).
Dùng Appium để kiểm thử đầy đủ luồng thêm giỏ và đặt hàng trên ứng dụng di động.
Giữ NUnit và JMeter đúng yêu cầu đề.”
Nếu giảng viên hỏi “vậy có lệch đề không?”, bạn chốt thêm 1 câu:

“Nhóm không đổi mục tiêu nghiệp vụ, chỉ đổi công cụ ở phần UI để phù hợp thực tế kỹ thuật của ShopeeFood hiện tại.”

Tài liệu này giúp bạn chuẩn bị và chạy đầy đủ 3 phần kiểm thử trong project:
1. UI automation (Appium)
2. Unit test (.NET/NUnit)
3. Performance test API menu (JMeter)

Ngoài ra có sẵn phần lấy số liệu để bạn đưa vào báo cáo Word.

## 1. Tổng quan bài tập

Project gồm 3 phần:
1. UI automation (Python + Appium) cho luồng đặt món trên app Android.
2. Unit tests (C# + NUnit) cho logic tính phí ship và tổng tiền.
3. Performance test API menu (Apache JMeter) với peak 500 và 1000 users.

## 2. Cấu trúc thư mục quan trọng

```text
FoodOrderSelenium/
  README.md
  run_full_3_parts.bat
  ui-tests/
	 .env
	 run_all.bat
	 run_ui_and_unit.bat
	 main.py
  unit-tests/
	 FoodOrder.Tests.csproj
	 runtime/ui_result.json
  performance-tests/
	 menu_api_load_test.jmx
	 run_mock_api.bat
	 run_500_users.bat
	 run_1000_users.bat
	 users.csv
	 results/
```

## 3. Chuẩn bị môi trường

### 3.1 Thành phần bắt buộc

1. Windows.
2. Java 17+ (để chạy JMeter).
3. .NET SDK 8+ (để chạy unit tests).
4. Android SDK + adb + Android Emulator (để chạy Appium UI test).
5. Appium server.
6. Apache JMeter (đã cài ở `D:\apache-jmeter-5.6.3`).

### 3.2 Kiểm tra nhanh trước khi chạy

Mở PowerShell tại thư mục gốc project và chạy:

```powershell
java -version
dotnet --version
Test-Path 'D:\apache-jmeter-5.6.3\bin\jmeter.bat'
```

Kỳ vọng:
1. Java hiển thị version.
2. Dotnet hiển thị version.
3. Dòng `Test-Path` trả về `True`.

### 3.3 Cấu hình file môi trường

Kiểm tra file `ui-tests/.env` có các biến JMeter như sau:

```dotenv
JMETER_BIN=D:\apache-jmeter-5.6.3\bin\jmeter.bat
API_PROTOCOL=http
API_HOST=127.0.0.1
API_PORT=5000
API_MENU_PATH=/api/menu
CONNECT_TIMEOUT=10000
RESPONSE_TIMEOUT=15000
MAX_RESPONSE_MS=2000
LOAD_DURATION_SEC=300
```

Lưu ý bảo mật:
1. Không commit tài khoản/mật khẩu trong `.env` lên GitHub.
2. Nếu đã lỡ lộ mật khẩu, đổi mật khẩu ngay.

## 4. Hướng dẫn chạy chi tiết

### 4.1 Chạy UI Appium riêng

```powershell
cd ui-tests
.\run_all.bat
```

Script sẽ tự:
1. Kiểm tra/tạo virtualenv.
2. Cài dependencies Python.
3. Kiểm tra Appium server.
4. Chạy luồng tự động trong `main.py`.

Kết quả đầu ra:
1. Log chạy trên terminal.
2. Ảnh chụp trong `ui-tests/screenshots`.

### 4.2 Chạy Unit test riêng

```powershell
cd unit-tests
dotnet test -c Release --nologo --verbosity minimal
```

Kết quả đầu ra:
1. Trạng thái pass/fail từng test.
2. Tổng kết số test pass/fail trên terminal.

### 4.3 Chạy liền mạch UI + Unit

```powershell
cd ui-tests
.\run_ui_and_unit.bat
```

Luồng thực hiện:
1. Chạy UI Appium flow.
2. Kiểm tra file runtime bridge.
3. Chạy unit tests.

File bridge quan trọng:
1. `unit-tests/runtime/ui_result.json`

## 5. Chạy performance test JMeter (phần quan trọng)

### 5.1 Chế độ miễn phí (khuyên dùng cho bài tập)

Chế độ này dùng API mock local nên không tốn tiền cloud.

Bước 1: Mở terminal A, chạy mock API.

```powershell
cd performance-tests
.\run_mock_api.bat
```

Ghi chú:
1. Nếu máy không nhận `python`, script đã có fallback chạy bằng PowerShell.
2. Khi thấy dòng `Mock menu API running at http://127.0.0.1:5000/api/menu` là API local đã sẵn sàng.

Bước 2: Mở terminal B, chạy test 500 users.

```powershell
cd performance-tests
.\run_500_users.bat
```

Bước 3: Chạy test 1000 users.

```powershell
cd performance-tests
.\run_1000_users.bat
```

Kết quả đầu ra:
1. `performance-tests/results/menu_500_html/index.html`
2. `performance-tests/results/menu_1000_html/index.html`
3. `performance-tests/results/menu_500.jtl`
4. `performance-tests/results/menu_1000.jtl`

### 5.2 Chế độ test API thật

Nếu muốn test API thật (staging/production-like), sửa trong `ui-tests/.env`:
1. `API_PROTOCOL`
2. `API_HOST`
3. `API_PORT`
4. `API_MENU_PATH`

Khuyến nghị:
1. Chạy ngoài giờ cao điểm.
2. Thống nhất trước với backend/devops.

## 6. Chạy toàn bộ 3 phần bằng 1 lệnh

Từ thư mục gốc project:

```powershell
.\run_full_3_parts.bat
```

Thứ tự chạy:
1. UI Appium + Unit.
2. JMeter 500 users.
3. JMeter 1000 users.

## 7. Cách đọc log JMeter

Trong output JMeter:
1. `summary +` là thống kê theo từng khoảng thời gian.
2. `summary =` là thống kê cộng dồn từ đầu bài test.
3. `Err: 0 (0.00%)` nghĩa là không có request lỗi ở khoảng đó.
4. `... end of run` nghĩa là test đã kết thúc hoàn toàn.

Ví dụ kết luận đúng:
1. "Trong phạm vi môi trường test hiện tại, chưa ghi nhận lỗi (error rate 0.00%)."

## 8. Lấy số liệu cho báo cáo Word

### 8.1 Các chỉ số cần đưa vào báo cáo

Với mỗi mức tải (500 và 1000 users), lấy:
1. Total requests.
2. Throughput (req/s).
3. Avg response time (ms).
4. Max response time (ms).
5. Error rate (%).
6. Duration (thời gian chạy).

Nguồn số liệu:
1. Dòng `summary = ...` cuối cùng trên terminal.
2. Hoặc mở file HTML report trong `performance-tests/results/.../index.html`.

### 8.2 Mẫu bảng để dán vào Word

| Test case | Users | Duration | Total requests | Throughput (req/s) | Avg (ms) | Max (ms) | Error rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| Menu API load | 500 | 300s | ... | ... | ... | ... | ... |
| Menu API load | 1000 | 300s | ... | ... | ... | ... | ... |

### 8.3 Mẫu đoạn mô tả kết quả trong báo cáo

"Nhóm thực hiện kiểm thử tải API Menu ở 2 mức peak users (500 và 1000). Kết quả cho thấy hệ thống xử lý ổn định trong phạm vi môi trường kiểm thử hiện tại, tỷ lệ lỗi quan sát được là 0.00%, throughput duy trì ổn định và thời gian phản hồi trung bình nằm trong ngưỡng chấp nhận cho bài tập."

Lưu ý cách viết học thuật:
1. Không viết tuyệt đối "hệ thống không bao giờ lỗi".
2. Nên viết "trong phạm vi test hiện tại, chưa ghi nhận lỗi".

## 9. Lỗi thường gặp và cách xử lý

1. Lỗi `Cannot find JMeter`.
	1. Kiểm tra `JMETER_BIN` trong `ui-tests/.env`.
	2. Kiểm tra file `D:\apache-jmeter-5.6.3\bin\jmeter.bat` có tồn tại.

2. Lỗi không chạy được `python`.
	1. Dùng virtualenv Python nếu có.
	2. Hoặc dùng `run_mock_api.bat` vì script đã có fallback PowerShell.

3. Mock API không lên.
	1. Kiểm tra cổng `5000` có bị chiếm.
	2. Tắt tiến trình cũ rồi chạy lại `run_mock_api.bat`.

4. Appium không kết nối.
	1. Kiểm tra Appium server đã chạy.
	2. Kiểm tra emulator và `ANDROID_UDID` trong `.env`.

## 10. Checklist nộp bài

1. Có log/screenshot UI chạy thành công.
2. Có kết quả unit tests pass.
3. Có 2 report JMeter (500 và 1000 users).
4. Có bảng số liệu tổng hợp trong Word.
5. Kết luận viết đúng chuẩn: "trong phạm vi test hiện tại".

## 11. Giải thích code theo từng file

Phần này dùng để bạn thuyết trình nhanh: mỗi file làm nhiệm vụ gì và liên kết với file nào.

### 11.1 Nhóm UI automation (Appium)

1. `ui-tests/main.py`
	1. Đây là file lõi của luồng mobile automation.
	2. Chức năng chính:
		1. Đọc cấu hình từ `.env` qua `AppConfig`.
		2. Kết nối Appium server, kiểm tra thiết bị Android và package app.
		3. Điều hướng luồng nghiệp vụ: mở app -> tìm món -> vào quán -> thêm giỏ -> xử lý đăng nhập nếu cần.
		4. Chụp screenshot khi lỗi và ở các bước quan trọng.
		5. Xuất dữ liệu runtime sang `unit-tests/runtime/ui_result.json` để unit tests đối chiếu.
	3. Điểm nên trình bày với giảng viên:
		1. Script có nhiều lớp fallback locator để giảm flaky test.
		2. Có cơ chế verify giỏ hàng tăng trước/sau thao tác.

2. `ui-tests/run_all.bat`
	1. Script chạy UI tự động 1 lệnh.
	2. Tự kiểm tra virtualenv, cài package từ `requirements.txt`, kiểm tra Appium/adb rồi gọi `main.py`.

3. `ui-tests/run_ui_and_unit.bat`
	1. Chạy pipeline UI -> Unit.
	2. Sau khi UI chạy xong sẽ kiểm tra file `ui_result.json` rồi mới chạy `dotnet test`.

4. `ui-tests/.env`
	1. Nơi cấu hình toàn bộ tham số chạy (Appium + JMeter).
	2. Các biến quan trọng UI: `SHOPEE_USER`, `SHOPEE_PASS`, `ANDROID_UDID`, `ADD_TO_CART_QTY`.

### 11.2 Nhóm Unit tests (NUnit)

1. `unit-tests/OrderCalculator.cs`
	1. Chứa business logic cốt lõi:
		1. `CalculateShippingFee(distanceKm)`.
		2. `CalculateTotal(foodPrice, quantity, distanceKm)`.
	2. Đây là nơi hiện thực công thức để test bằng NUnit.

2. `unit-tests/ShippingFeeTests.cs`
	1. Kiểm thử phí ship theo các mốc khoảng cách (2km, 4km, 6km, 11km).
	2. Mục tiêu: xác nhận công thức phí ship đúng theo đề bài.

3. `unit-tests/TotalPriceTests.cs`
	1. Kiểm thử công thức tổng tiền = tiền món * số lượng + phí ship.

4. `unit-tests/UiToUnitBridgeTests.cs`
	1. Đọc `runtime/ui_result.json` do UI xuất ra.
	2. So sánh giá trị hiển thị từ UI với giá trị tính lại bởi `OrderCalculator`.
	3. Ý nghĩa: chứng minh tính nhất quán giữa UI và business logic.

5. `unit-tests/runtime/ui_result.json`
	1. File dữ liệu runtime do UI ghi ra.
	2. Dùng làm input cho bridge test ở trên.

### 11.3 Nhóm Performance tests (JMeter)

1. `performance-tests/menu_api_load_test.jmx`
	1. Test plan JMeter chính.
	2. Gồm:
		1. Thread Group theo số users (500/1000).
		2. HTTP Request đến API menu.
		3. Assertion kiểm tra HTTP code 200 và thời gian phản hồi.
		4. Ghi kết quả ra JTL và HTML report.

2. `performance-tests/run_500_users.bat`
	1. Chạy test 500 users non-GUI.
	2. Tự đọc biến cấu hình từ `ui-tests/.env`.

3. `performance-tests/run_1000_users.bat`
	1. Chạy test 1000 users non-GUI.
	2. Tương tự script 500 nhưng tăng số users.

4. `performance-tests/run_mock_api.bat`
	1. Khởi động API mock local miễn phí tại `http://127.0.0.1:5000/api/menu`.
	2. Có fallback PowerShell nếu máy không chạy được Python launcher.

5. `performance-tests/mock_menu_api.py`
	1. Server mock đơn giản trả danh sách món JSON.
	2. Dùng để benchmark không tốn chi phí cloud.

6. `performance-tests/users.csv`
	1. Dữ liệu đầu vào cho JMeter (token, query).
	2. Giúp mô phỏng request có dữ liệu thay đổi.

### 11.4 File điều phối tổng

1. `run_full_3_parts.bat`
	1. Chạy full pipeline theo thứ tự:
		1. UI + Unit.
		2. JMeter 500.
		3. JMeter 1000.
	2. Dùng khi demo hoặc chạy cuối để lấy đủ bằng chứng nộp bài.

### 11.5 Luồng dữ liệu tổng từ đầu đến cuối

1. UI Appium chạy nghiệp vụ thực tế trên app và tạo dữ liệu runtime.
2. Unit tests dùng dữ liệu runtime để xác nhận công thức nghiệp vụ.
3. JMeter kiểm tra khả năng chịu tải API menu ở peak users.
4. Báo cáo Word tổng hợp từ:
	1. Log UI + screenshots.
	2. Kết quả NUnit.
	3. HTML/JTL của JMeter.

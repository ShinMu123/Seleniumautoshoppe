# JMeter Menu API Load Test

This folder is independent from Appium/Selenium tests in ui-tests.
Use it to load-test menu API at peak traffic 500-1000 users.

## 1) Prepare

1. Install Apache JMeter (example: C:\apache-jmeter-5.6.3).
2. Edit one of these files:
- run_500_users.bat
- run_1000_users.bat
3. Replace placeholders:
- your-api-host.com
- /api/menu (if your real endpoint is different)

## 2) Configure test data

Edit users.csv:
- token: bearer token without "Bearer " prefix
- query: sample menu search text

If API does not require auth, keep token empty in csv.

## 3) Run

For 500 users:

run_500_users.bat

For 1000 users:

run_1000_users.bat

## 4) Output

- JTL files: results/menu_500.jtl, results/menu_1000.jtl
- HTML reports:
  - results/menu_500_html/index.html
  - results/menu_1000_html/index.html

## 5) KPI suggestions

- Error rate < 1%
- P95 response time < 2000ms (or your SLO)
- Throughput stable during full duration

## 6) Notes for your current project

Your current UI tests in ui-tests/main.py run on mobile app via Appium.
So JMeter should target backend API directly (menu endpoint), not the app UI.
This is normal and is the correct way for peak load testing.

## 7) Zero-cost mode (for assignment)

If you do not want to spend money on cloud API traffic, use local mock API:

1. Start mock API:

run_mock_api.bat

2. In another terminal, run JMeter:

run_500_users.bat
run_1000_users.bat

Default env is configured to local endpoint:
- API_PROTOCOL=http
- API_HOST=127.0.0.1
- API_PORT=5000
- API_MENU_PATH=/api/menu

@echo off
REM Start local mock menu API (Python first, PowerShell fallback) for zero-cost load tests.
setlocal

cd /d "%~dp0"

set "PYTHON_EXE=..\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

echo [INFO] Starting local mock menu API on http://127.0.0.1:5000/api/menu
"%PYTHON_EXE%" mock_menu_api.py
if not errorlevel 1 goto :eof

echo [WARN] Python launcher failed. Falling back to PowerShell mock API server...
powershell -NoProfile -Command ^
	"$listener = New-Object System.Net.HttpListener;" ^
	"$listener.Prefixes.Add('http://127.0.0.1:5000/');" ^
	"$listener.Start();" ^
	"Write-Output 'Mock menu API running at http://127.0.0.1:5000/api/menu';" ^
	"$menu = @(@{id=1;name='Tra sua truyen thong';price=28000},@{id=2;name='Tra dao cam sa';price=35000},@{id=3;name='Bun bo';price=45000},@{id=4;name='Com ga';price=42000});" ^
	"try { while ($listener.IsListening) {" ^
	"  $ctx = $listener.GetContext();" ^
	"  $path = $ctx.Request.Url.AbsolutePath;" ^
	"  if ($path -eq '/api/menu') {" ^
	"    $q = $ctx.Request.QueryString['q'];" ^
	"    $items = $menu;" ^
	"    if ($q) { $items = $menu | Where-Object { $_.name.ToLower().Contains($q.ToLower()) } }" ^
	"    $payload = @{success=$true;count=$items.Count;items=$items} | ConvertTo-Json -Depth 5;" ^
	"    $code = 200;" ^
	"  } else {" ^
	"    $payload = '{\"error\":\"not_found\"}';" ^
	"    $code = 404;" ^
	"  }" ^
	"  $bytes = [System.Text.Encoding]::UTF8.GetBytes($payload);" ^
	"  $ctx.Response.StatusCode = $code;" ^
	"  $ctx.Response.ContentType = 'application/json; charset=utf-8';" ^
	"  $ctx.Response.ContentLength64 = $bytes.Length;" ^
	"  $ctx.Response.OutputStream.Write($bytes,0,$bytes.Length);" ^
	"  $ctx.Response.OutputStream.Close();" ^
	" } } finally { $listener.Stop(); $listener.Close(); }"

endlocal

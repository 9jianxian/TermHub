@echo off
echo ========================================
echo   术语通 TermHub - 启动脚本
echo ========================================
echo.
echo [1/3] 检查Python环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误：没有检测到Python，请先安装Python 3.8+
    echo 下载地址：https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)
echo Python环境正常
echo.
echo [2/3] 检查并安装依赖...
pip show flask >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在安装Flask，请稍候...
    pip install flask -i https://pypi.tuna.tsinghua.edu.cn/simple
    if %errorlevel% neq 0 (
        echo 安装失败，请检查网络连接
        pause
        exit /b 1
    )
    echo Flask安装成功
) else (
    echo Flask已安装
)
pip show edge-tts >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在安装语音合成模块edge-tts，请稍候...
    pip install edge-tts -i https://pypi.tuna.tsinghua.edu.cn/simple
    if %errorlevel% neq 0 (
        echo 安装失败，请检查网络连接
        pause
        exit /b 1
    )
    echo edge-tts安装成功
) else (
    echo edge-tts已安装
)
echo.
echo [3/3] 启动网站...
echo ========================================
echo   网站启动成功！
echo   请在浏览器中打开：http://localhost:5001/
echo ========================================
echo.
echo 提示：关闭此窗口即可停止网站
echo.
python app.py
pause

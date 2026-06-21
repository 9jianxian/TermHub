#!/bin/bash

# 设置终端编码，防止中文乱码
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

echo "========================================"
echo "  网络安全词汇动态网站 - 启动脚本"
echo "========================================"
echo ""

echo "[1/3] 检查Python环境..."
if ! command -v python3 &> /dev/null; then
    echo "错误：没有检测到Python3，请先安装Python 3.8+"
    echo "Mac用户：brew install python3"
    echo "Linux用户：sudo apt install python3 python3-pip"
    echo ""
    read -p "按回车键退出"
    exit 1
fi
echo "Python环境正常"
echo ""

echo "[2/3] 检查并安装依赖..."
if ! python3 -c "import flask" &> /dev/null; then
    echo "正在安装Flask，请稍候..."
    pip3 install flask -i https://pypi.tuna.tsinghua.edu.cn/simple
    if [ $? -ne 0 ]; then
        echo "安装失败，请检查网络连接"
        read -p "按回车键退出"
        exit 1
    fi
    echo "Flask安装成功"
else
    echo "Flask已安装"
fi

if ! python3 -c "import edge_tts" &> /dev/null; then
    echo "正在安装语音合成模块edge-tts，请稍候..."
    pip3 install edge-tts -i https://pypi.tuna.tsinghua.edu.cn/simple
    if [ $? -ne 0 ]; then
        echo "安装失败，请检查网络连接"
        read -p "按回车键退出"
        exit 1
    fi
    echo "edge-tts安装成功"
else
    echo "edge-tts已安装"
fi
echo ""

echo "[3/3] 启动网站..."
echo "========================================"
echo "  网站启动成功！"
echo "  请在浏览器中打开：http://localhost:5001/"
echo "========================================"
echo ""
echo "提示：按 Ctrl+C 停止网站"
echo ""

python3 app.py

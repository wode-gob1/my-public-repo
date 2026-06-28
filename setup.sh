#!/bin/bash
# ============================================
# 自动安装脚本 — 每次开机自动运行
# 你可以修改这个文件，添加你需要的软件和配置
# ============================================

echo ">>> 开始自动安装..."

# ---- Python 库 ----
# 把你要用的 Python 库写在下面（每行一个）
echo ">>> 安装 Python 库..."
pip3 install --quiet \
  requests \
  numpy \
  pandas

# ---- Node.js 全局包 ----
# echo ">>> 安装 Node.js 全局包..."
# npm install -g typescript

# ---- 下载学习资料 ----
# echo ">>> 下载学习资料..."
# wget -q https://example.com/资料.zip -O ~/资料.zip
# unzip -q ~/资料.zip -d ~/

# ---- 自定义配置 ----
# echo ">>> 配置环境..."
# alias ll='ls -la'
# export MY_VAR="hello"

echo ">>> 自动安装完成！"
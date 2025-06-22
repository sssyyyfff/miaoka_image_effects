import os
import sys
import subprocess
import importlib.util
import logging
import traceback

logger = logging.getLogger(__name__)
REQUIREMENTS = ["numpy", "Pillow", "opencv-python-headless"]

def is_installed(package):
    """检查包是否已安装"""
    try:
        if package == "opencv-python-headless":
            return importlib.util.find_spec("cv2") is not None
        return importlib.util.find_spec(package) is not None
    except ImportError:
        return False

def check_dependencies():
    """检查并报告依赖状态"""
    missing = []
    for package in REQUIREMENTS:
        if not is_installed(package):
            missing.append(package)
    
    if missing:
        logger.warning(f"喵咔图像效果工具箱 (MIAOKA) 缺少依赖: {', '.join(missing)}")
        logger.warning("请手动运行插件目录中的 install.py 安装依赖")
        return False
    return True

# 在插件加载时检查依赖
if not check_dependencies():
    logger.error("喵咔图像效果工具箱 (MIAOKA) 依赖未满足，部分功能可能无法使用")

# 导入主脚本
try:
    from .scripts.miaoka_image_effects import Script
except ImportError as e:
    logger.error(f"导入主脚本失败: {e}")
    logger.error(traceback.format_exc())
import os
import sys
import subprocess
import time
from modules import shared, scripts

# 依赖列表
REQUIREMENTS = [
    "numpy",
    "Pillow",
    "opencv-python-headless"
]

def is_installed(package):
    """检查包是否已安装"""
    try:
        # 处理 opencv-python-headless 的特殊情况
        if package == "opencv-python-headless":
            import cv2
            return True
        
        __import__(package)
        return True
    except ImportError:
        return False

def run_install():
    """运行依赖安装"""
    print("\n🐱 喵咔图像效果工具箱 (MIAOKA) 正在安装依赖...")
    
    python = sys.executable
    if not python:
        print("❌ 错误: 找不到 Python 解释器")
        return
    
    # 安装每个依赖
    for package in REQUIREMENTS:
        if is_installed(package):
            print(f"✅ {package} 已安装")
            continue
            
        try:
            print(f"⬇️ 正在安装 {package}...")
            result = subprocess.run(
                [python, '-m', 'pip', 'install', package],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if result.returncode == 0:
                print(f"✅ {package} 安装成功")
            else:
                print(f"❌ {package} 安装失败:")
                print(result.stderr)
                
        except subprocess.CalledProcessError as e:
            print(f"❌ {package} 安装失败 (错误代码 {e.returncode}):")
            print(e.stderr)
        except Exception as e:
            print(f"❌ {package} 安装时发生未知错误:")
            print(str(e))
    
    print("\n🐱 喵咔图像效果工具箱 (MIAOKA) 依赖安装完成!")
    print("⚠️ 请重启 WebUI 以使更改生效")
    time.sleep(3)

# 当脚本被导入时自动运行安装
run_install()
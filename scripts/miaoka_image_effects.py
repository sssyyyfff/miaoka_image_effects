import os
import time
import sys
import subprocess
import numpy as np
from PIL import Image, ImageFilter, ImageOps
import gradio as gr
import modules.scripts as scripts
from modules.processing import StableDiffusionProcessing, process_images
from modules import shared

# 依赖检查
CV2_AVAILABLE = False
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    # 提供更明确的错误信息
    print("❌ 喵咔图像效果工具箱 (MIAOKA) 警告: OpenCV 未安装，部分效果将不可用")
    print("💡 请手动安装所需依赖")
    cv2 = None

class MiaokaImageEffects(scripts.Script):
    def title(self):
        return "喵咔图像效果工具箱 (MIAOKA)"
    
    def show(self, is_img2img):
        return True
    
    def ui(self, is_img2img):
        with gr.Accordion("喵咔图像效果工具箱 (MIAOKA)", open=False):
            # 效果参数部分
            with gr.Row():
                effect_strength = gr.Slider(
                    minimum=0,
                    maximum=100,
                    step=1,
                    label="效果强度",
                    value=15,
                )
                
            with gr.Row():
                effect_type = gr.Dropdown(
                    choices=[
                        "无效果",
                        "高斯噪点",
                        "椒盐噪点",
                        "均匀噪点",
                        "斑点噪点",
                        "高斯模糊",
                        "运动模糊",
                        "锐化",
                        "边缘检测",
                        "油画效果",
                        "铅笔画",
                        "怀旧棕调",
                        "反色",
                        "像素化",
                        "雨滴效果",
                        "胶片颗粒",
                        "素描效果"
                    ],
                    label="效果类型",
                    value="无效果"
                )
                
            with gr.Row():
                apply_to = gr.Radio(
                    choices=["所有图像", "仅第一张"],
                    label="应用范围",
                    value="所有图像",
                )
                
            with gr.Row():
                show_compare = gr.Checkbox(label="显示对比图", value=True)
                
            with gr.Row():
                save_originals = gr.Checkbox(label="保存原始图像", value=True)
                save_processed = gr.Checkbox(label="保存处理图像", value=True)
                
            with gr.Row():
                preset_btn_1 = gr.Button("轻微 (10%)")
                preset_btn_2 = gr.Button("中等 (30%)")
                preset_btn_3 = gr.Button("强烈 (60%)")
                
            def set_preset(val):
                return gr.update(value=val)
            
            preset_btn_1.click(fn=lambda: set_preset(10), outputs=effect_strength)
            preset_btn_2.click(fn=lambda: set_preset(30), outputs=effect_strength)
            preset_btn_3.click(fn=lambda: set_preset(60), outputs=effect_strength)

        return [effect_strength, effect_type, apply_to, show_compare, save_originals, save_processed]
    
    def run(self, p: StableDiffusionProcessing, effect_strength, effect_type, apply_to, show_compare, save_originals, save_processed):
        # 处理原始图像
        result = process_images(p)
        
        # 如果没有选择效果，直接返回原始结果
        if effect_type == "无效果" or effect_strength <= 0:
            return result
        
        # 获取当前时间戳用于文件名
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        # 创建原始图像和处理后图像的目录
        base_outdir = p.outpath_samples
        outdir_orig = os.path.join(base_outdir, "original")
        outdir_processed = os.path.join(base_outdir, "processed")
        
        if save_originals:
            os.makedirs(outdir_orig, exist_ok=True)
        if save_processed:
            os.makedirs(outdir_processed, exist_ok=True)
        
        # 处理图像并保存
        processed_images = []
        combined_images = []
        
        for i, img in enumerate(result.images):
            try:
                # 保存原始图像
                if save_originals:
                    orig_filename = f"{timestamp}_{p.seed}_{i:03}_original.png"
                    orig_path = os.path.join(outdir_orig, orig_filename)
                    img.save(orig_path)
                
                # 检查是否应处理此图像
                if apply_to == "仅第一张" and i > 0:
                    processed_images.append(img)
                    continue
                
                # 应用效果
                processed_img = self.apply_effect(img, effect_type, effect_strength)
                processed_images.append(processed_img)
                
                # 保存处理后的图像
                if save_processed:
                    processed_filename = f"{timestamp}_{p.seed}_{i:03}_{effect_type}.png"
                    processed_path = os.path.join(outdir_processed, processed_filename)
                    processed_img.save(processed_path)
                
                # 创建对比图
                if show_compare:
                    combined = Image.new("RGB", (img.width * 2, img.height))
                    combined.paste(img, (0, 0))
                    combined.paste(processed_img, (img.width, 0))
                    combined_images.append(combined)
                    
            except Exception as e:
                print(f"❌ 喵咔图像处理失败 (image {i}): {e}")
                processed_images.append(img)  # 出错时返回原始图像
                continue
        
        # 更新结果图像
        if show_compare and combined_images:
            # 添加处理后的图像和对比图
            result.images = processed_images + combined_images
        else:
            # 只添加处理后的图像
            result.images = processed_images
        
        # 添加日志信息
        print(f"\n🐱 喵咔图像效果工具箱 (MIAOKA) 已处理 {len(processed_images)} 张图像")
        if save_originals:
            print(f"📁 原始图像保存至: {outdir_orig}")
        if save_processed:
            print(f"🎨 效果图像保存至: {outdir_processed}")
        print(f"✨ 效果类型: {effect_type}, 强度: {effect_strength}%\n")
        
        return result
    
    def apply_effect(self, image, effect_type, strength):
        """应用指定的效果到图像 (喵咔 MIAOKA)"""
        # 确保图像是RGB模式
        if image.mode != "RGB":
            image = image.convert("RGB")
            
        # 根据效果类型选择处理方法
        if effect_type == "高斯噪点":
            return self.add_gaussian_noise(image, strength)
        elif effect_type == "椒盐噪点":
            return self.add_salt_pepper_noise(image, strength)
        elif effect_type == "均匀噪点":
            return self.add_uniform_noise(image, strength)
        elif effect_type == "斑点噪点":
            return self.add_speckle_noise(image, strength)
        elif effect_type == "高斯模糊":
            return self.apply_gaussian_blur(image, strength)
        elif effect_type == "运动模糊":
            return self.apply_motion_blur(image, strength)
        elif effect_type == "锐化":
            return self.apply_sharpen(image, strength)
        elif effect_type == "边缘检测":
            return self.apply_edge_detection(image, strength)
        elif effect_type == "油画效果":
            return self.apply_oil_painting(image, strength)
        elif effect_type == "铅笔画":
            return self.apply_pencil_sketch(image, strength)
        elif effect_type == "怀旧棕调":
            return self.apply_sepia(image, strength)
        elif effect_type == "反色":
            return self.apply_invert(image)
        elif effect_type == "像素化":
            return self.apply_pixelate(image, strength)
        elif effect_type == "雨滴效果":
            return self.apply_rain_effect(image, strength)
        elif effect_type == "胶片颗粒":
            return self.apply_film_grain(image, strength)
        elif effect_type == "素描效果":
            return self.apply_sketch(image, strength)
        else:
            return image
    
    # =================== 喵咔图像处理效果 ===================
    # 噪点效果
    def add_gaussian_noise(self, image, strength):
        """添加高斯噪点 (喵咔 MIAOKA)"""
        img_array = np.array(image).astype(np.float32) / 255.0
        noise = np.random.normal(0, strength / 100.0, img_array.shape)
        noisy_array = np.clip(img_array + noise, 0, 1) * 255
        return Image.fromarray(noisy_array.astype(np.uint8))
    
    def add_salt_pepper_noise(self, image, strength):
        """添加椒盐噪点 (喵咔 MIAOKA)"""
        img_array = np.array(image)
        output = np.copy(img_array)
        prob = strength / 500.0
        rand = np.random.rand(*img_array.shape[:2])
        salt_mask = rand < prob
        pepper_mask = rand > (1 - prob)
        output[salt_mask] = 255
        output[pepper_mask] = 0
        return Image.fromarray(output)
    
    def add_uniform_noise(self, image, strength):
        """添加均匀噪点 (喵咔 MIAOKA)"""
        img_array = np.array(image).astype(np.float32) / 255.0
        noise = np.random.uniform(-strength / 100.0, strength / 100.0, img_array.shape)
        noisy_array = np.clip(img_array + noise, 0, 1) * 255
        return Image.fromarray(noisy_array.astype(np.uint8))
    
    def add_speckle_noise(self, image, strength):
        """添加斑点噪点 (喵咔 MIAOKA)"""
        img_array = np.array(image).astype(np.float32) / 255.0
        noise = np.random.randn(*img_array.shape) * (strength / 100.0)
        noisy_array = np.clip(img_array + img_array * noise, 0, 1) * 255
        return Image.fromarray(noisy_array.astype(np.uint8))
    
    # 滤镜效果
    def apply_gaussian_blur(self, image, strength):
        """应用高斯模糊 (喵咔 MIAOKA)"""
        radius = max(0.5, strength / 20)
        return image.filter(ImageFilter.GaussianBlur(radius=radius))
    
    def apply_motion_blur(self, image, strength):
        """应用运动模糊 (喵咔 MIAOKA)"""
        if not CV2_AVAILABLE:
            print("⚠️ 喵咔: 运动模糊需要OpenCV，使用高斯模糊代替")
            return self.apply_gaussian_blur(image, strength)
        
        try:
            img_array = np.array(image)
            size = int(strength / 5) + 1
            kernel = np.zeros((size, size))
            kernel[int((size-1)/2), :] = np.ones(size)
            kernel = kernel / size
            blurred = cv2.filter2D(img_array, -1, kernel)
            return Image.fromarray(blurred)
        except Exception as e:
            print(f"⚠️ 喵咔: 运动模糊失败: {e}")
            return image
    
    def apply_sharpen(self, image, strength):
        """应用锐化 (喵咔 MIAOKA)"""
        return image.filter(ImageFilter.UnsharpMask(radius=2, percent=strength, threshold=3))
    
    def apply_edge_detection(self, image, strength):
        """应用边缘检测 (喵咔 MIAOKA)"""
        if not CV2_AVAILABLE:
            print("⚠️ 喵咔: 边缘检测需要OpenCV，使用Sobel滤镜代替")
            return image.filter(ImageFilter.FIND_EDGES)
        
        try:
            img_array = np.array(image)
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            edges = cv2.Canny(gray, strength, strength * 2)
            return Image.fromarray(edges)
        except Exception as e:
            print(f"⚠️ 喵咔: 边缘检测失败: {e}")
            return image
    
    def apply_oil_painting(self, image, strength):
        """应用油画效果 (喵咔 MIAOKA)"""
        if not CV2_AVAILABLE:
            print("⚠️ 喵咔: 油画效果需要OpenCV，使用海报化代替")
            return image.filter(ImageFilter.MedianFilter(size=3))
        
        try:
            img_array = np.array(image)
            size = max(1, int(strength / 20))
            oil = cv2.xphoto.oilPainting(img_array, size=size, dynRatio=1)
            return Image.fromarray(oil)
        except Exception as e:
            print(f"⚠️ 喵咔: 油画效果失败: {e}")
            return image
    
    def apply_pencil_sketch(self, image, strength):
        """应用铅笔画效果 (喵咔 MIAOKA)"""
        if not CV2_AVAILABLE:
            print("⚠️ 喵咔: 铅笔画效果需要OpenCV，使用轮廓滤镜代替")
            return image.filter(ImageFilter.CONTOUR)
        
        try:
            img_array = np.array(image)
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            inverted = 255 - gray
            blurred = cv2.GaussianBlur(inverted, (21, 21), 0)
            pencil = cv2.divide(gray, 255 - blurred, scale=256)
            return Image.fromarray(pencil)
        except Exception as e:
            print(f"⚠️ 喵咔: 铅笔画效果失败: {e}")
            return image
    
    def apply_sepia(self, image, strength):
        """应用怀旧棕调 (喵咔 MIAOKA)"""
        sepia_filter = np.array([
            [0.393 + strength/300, 0.769, 0.189],
            [0.349, 0.686 + strength/300, 0.168],
            [0.272, 0.534, 0.131 + strength/300]
        ])
        img_array = np.array(image).astype(np.float32) / 255.0
        sepia = np.dot(img_array, sepia_filter.T)
        sepia = np.clip(sepia, 0, 1) * 255
        return Image.fromarray(sepia.astype(np.uint8))
    
    def apply_invert(self, image):
        """应用反色 (喵咔 MIAOKA)"""
        return ImageOps.invert(image)
    
    def apply_pixelate(self, image, strength):
        """应用像素化 (喵咔 MIAOKA)"""
        size = max(1, int(strength / 10))
        small = image.resize((image.width // size, image.height // size), Image.NEAREST)
        return small.resize(image.size, Image.NEAREST)
    
    def apply_rain_effect(self, image, strength):
        """应用雨滴效果 (喵咔 MIAOKA)"""
        if not CV2_AVAILABLE:
            print("⚠️ 喵咔: 雨滴效果需要OpenCV，跳过效果")
            return image
        
        try:
            img_array = np.array(image)
            h, w, _ = img_array.shape
            rain_layer = np.zeros((h, w, 4), dtype=np.uint8)
            num_drops = int(strength * w * h / 500)
            
            for _ in range(num_drops):
                x, y = np.random.randint(0, w), np.random.randint(0, h)
                length = np.random.randint(5, 15)
                width = np.random.randint(1, 3)
                brightness = np.random.randint(150, 255)
                cv2.line(rain_layer, (x, y), (x, y + length), 
                        (brightness, brightness, brightness, 100), width)
            
            background = Image.fromarray(img_array).convert("RGBA")
            foreground = Image.fromarray(rain_layer)
            return Image.alpha_composite(background, foreground).convert("RGB")
        except Exception as e:
            print(f"⚠️ 喵咔: 雨滴效果失败: {e}")
            return image
    
    def apply_film_grain(self, image, strength):
        """应用胶片颗粒效果 (喵咔 MIAOKA)"""
        img_array = np.array(image).astype(np.float32) / 255.0
        noise = np.random.normal(0, strength / 200.0, img_array.shape)
        noisy_array = np.clip(img_array + noise, 0, 1) * 255
        result = Image.fromarray(noisy_array.astype(np.uint8))
        return result.filter(ImageFilter.GaussianBlur(radius=0.5))
    
    def apply_sketch(self, image, strength):
        """应用素描效果 (喵咔 MIAOKA)"""
        if not CV2_AVAILABLE:
            print("⚠️ 喵咔: 素描效果需要OpenCV，使用轮廓滤镜代替")
            return image.filter(ImageFilter.CONTOUR)
        
        try:
            img_array = np.array(image)
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            inverted = 255 - gray
            blurred = cv2.GaussianBlur(inverted, (21, 21), 0)
            sketch = cv2.divide(gray, 255 - blurred, scale=256)
            return Image.fromarray(sketch).convert("RGB")
        except Exception as e:
            print(f"⚠️ 喵咔: 素描效果失败: {e}")
            return image
import os
import time
import sys
import subprocess
import numpy as np
from PIL import Image, ImageFilter, ImageOps
import gradio as gr
import modules.scripts as scripts
from modules.processing import StableDiffusionProcessing, process_images

# Forge Classic / Neo 检测
# Neo 对 selectable Script 的生成流程进行了较多底层改动；在 Neo 中使用
# AlwaysVisible + postprocess()，让 WebUI 完成采样后再处理图片，避免插件
# 自己再次进入 process_images()。A1111 保留原来的 selectable Script 行为。
try:
    import importlib.util
    IS_FORGE = importlib.util.find_spec("modules_forge") is not None
except Exception:
    IS_FORGE = False
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
        # A1111：保持原来的 Scripts 下拉菜单行为
        # Forge Classic / Neo：改为 AlwaysVisible，通过 postprocess() 处理已生成图片
        if IS_FORGE:
            return scripts.AlwaysVisible
        return True
    
    def ui(self, is_img2img):
        """A1111 / Forge Classic / Neo 通用 UI。
        Neo 使用 AlwaysVisible + postprocess；A1111 仍可作为 Script 使用。
        """
        # 旧版效果 + 新增效果。顺序即默认处理管线顺序。
        self.effect_names = [
            "高斯噪点 Gaussian Noise", "椒盐噪点 Salt & Pepper Noise", "均匀噪点 Uniform Noise", "斑点噪点 Speckle Noise",
            "高斯模糊 Gaussian Blur", "运动模糊 Motion Blur", "锐化 Sharpen", "边缘检测 Edge Detection", "油画效果 Oil Painting",
            "铅笔画 Pencil Sketch", "怀旧棕调 Sepia", "反色 Invert", "像素化 Pixelate", "雨滴效果 Rain Drops",
            "胶片颗粒 Film Grain", "素描效果 Sketch",
            "曝光 Exposure", "亮度 Brightness", "对比度 Contrast", "饱和度 Saturation", "鲜艳度 Vibrance",
            "色温 Temperature", "色调 Tint", "高光 Highlights", "阴影 Shadows", "清晰度 Clarity",
            "智能锐化 Smart Sharpen", "局部对比度 Local Contrast", "边缘保护降噪 Edge-Preserving Denoise", "光晕 Bloom",
            "柔光 Soft Light", "暗角 Vignette", "褪色 Fade", "色彩平衡 Color Balance", "电影色调 Cinematic Tone",
            "HDR 高动态范围", "景深柔化 Depth Softening", "镜头模糊 Lens Blur", "色差 Chromatic Aberration", "RGB 分离 RGB Split"
        ]
        # 每项独立强度；0 = 不启用。
        with gr.Accordion("🐱 喵咔图像效果工具箱 (MIAOKA)", open=False):
            gr.Markdown("**多效果后处理管线** · 勾选多个效果后按顺序叠加。每个效果独立控制强度。")
            with gr.Row():
                effect_select = gr.CheckboxGroup(
                    choices=self.effect_names,
                    label="启用效果（可多选）",
                    value=[],
                    info="建议从 3～20% 开始；效果会按下方管线顺序依次处理。"
                )
            with gr.Row():
                apply_to = gr.Radio(["所有图像", "仅第一张"], label="应用范围", value="所有图像")
                show_compare = gr.Checkbox(label="显示对比图", value=True)
            with gr.Row():
                save_originals = gr.Checkbox(label="保存原始图像", value=True)
                save_processed = gr.Checkbox(label="保存处理图像", value=True)

            with gr.Accordion("🎚️ 效果强度（每项独立）", open=False):
                sliders = []
                # 按类别分组，避免 39 个控件挤成一列。
                groups = [
                    ("原有效果 Original Effects", self.effect_names[:16]),
                    ("基础调整 Basic Adjustments", self.effect_names[16:24]),
                    ("细节增强 Detail Enhancement", self.effect_names[24:28]),
                    ("光影效果 Lighting", self.effect_names[28:32]),
                    ("风格与镜头 Style & Lens", self.effect_names[32:])
                ]
                for title, names in groups:
                    with gr.Accordion(title, open=False):
                        for name in names:
                            sliders.append(gr.Slider(0, 100, value=0, step=1, label=name))

            with gr.Row():
                preset_btn_1 = gr.Button("🌱 动漫柔和 Anime Soft")
                preset_btn_2 = gr.Button("🎬 电影感 Cinematic")
                preset_btn_3 = gr.Button("✨ Dogma 收尾 Dogma Finish")
                preset_btn_4 = gr.Button("🧹 清空效果 Clear")

            def _preset_values(vals):
                # 预设必须同时勾选效果，否则后处理管线会认为没有启用任何效果。
                selected = [n for n in self.effect_names if vals.get(n, 0) > 0]
                return [selected] + [vals.get(n, 0) for n in self.effect_names]

            def preset_soft():
                vals = {"鲜艳度 Vibrance": 10, "高光 Highlights": 8, "阴影 Shadows": 5, "清晰度 Clarity": 10, "智能锐化 Smart Sharpen": 5, "光晕 Bloom": 5, "胶片颗粒 Film Grain": 2}
                return _preset_values(vals)

            def preset_cine():
                vals = {"曝光 Exposure": 2, "对比度 Contrast": 12, "鲜艳度 Vibrance": 8, "色温 Temperature": 2, "高光 Highlights": 8, "阴影 Shadows": 6, "清晰度 Clarity": 14, "光晕 Bloom": 5, "暗角 Vignette": 8, "褪色 Fade": 4}
                return _preset_values(vals)

            def preset_dogma():
                vals = {"清晰度 Clarity": 8, "智能锐化 Smart Sharpen": 6, "局部对比度 Local Contrast": 7, "边缘保护降噪 Edge-Preserving Denoise": 8, "胶片颗粒 Film Grain": 2, "光晕 Bloom": 3}
                return _preset_values(vals)

            def clear_all():
                return [[]] + [0 for _ in self.effect_names]

            preset_outputs = [effect_select, *sliders]
            preset_btn_1.click(fn=preset_soft, outputs=preset_outputs)
            preset_btn_2.click(fn=preset_cine, outputs=preset_outputs)
            preset_btn_3.click(fn=preset_dogma, outputs=preset_outputs)
            preset_btn_4.click(fn=clear_all, outputs=preset_outputs)

        # 参数：选择项 + 39 个独立强度 + 其它选项。
        return [effect_select, *sliders, apply_to, show_compare, save_originals, save_processed]

    def run(self, p: StableDiffusionProcessing, effect_select, *args):
        """A1111 selectable Script 路径。"""
        result = process_images(p)
        return self._process_from_args(p, result, effect_select, args)

    def setup(self, p, effect_select, *args):
        # 每次生成开始时重置 Neo 的逐图状态，避免上一批次的索引/目录状态串到下一次生成。
        self._neo_dirs_ready = False
        self._neo_image_index = 0
        self._neo_timestamp = time.strftime("%Y%m%d_%H%M%S")

    def postprocess_image(self, p, pp, effect_select, *args):
        """Forge Classic / Neo：逐张处理已经生成的最终图片。

        Neo 的 ScriptRunner 明确提供 postprocess_image()，它比在 postprocess()
        中整体替换 Processed.images 更可靠，也能避免不同 Forge 分支对
        Processed 生命周期的差异导致“UI 有了但效果不执行”。
        """
        try:
            n = len(getattr(self, "effect_names", [])) or 39
            strengths = list(args[:n])
            strengths += [0] * max(0, n - len(strengths))
            rest = list(args[n:])
            apply_to = rest[0] if len(rest) > 0 else "所有图像"
            show_compare = rest[1] if len(rest) > 1 else True
            save_originals = rest[2] if len(rest) > 2 else True
            save_processed = rest[3] if len(rest) > 3 else True
            selected = set(effect_select or [])
            pipeline = [(name, float(strengths[i] or 0)) for i, name in enumerate(self.effect_names)
                        if name in selected and float(strengths[i] or 0) > 0]
            if not pipeline:
                return

            # postprocess_image 没有可靠的 batch index 参数时，按已处理数量记录。
            idx = int(getattr(self, "_neo_image_index", 0))
            self._neo_image_index = idx + 1
            if apply_to == "仅第一张" and idx > 0:
                return

            image = getattr(pp, "image", None)
            if image is None:
                return
            if not isinstance(image, Image.Image):
                if isinstance(image, np.ndarray):
                    image = Image.fromarray(image)
                else:
                    return

            self._neo_prepare_output_dirs(p, save_originals, save_processed)
            timestamp = getattr(self, "_neo_timestamp", time.strftime("%Y%m%d_%H%M%S"))
            base_seed = getattr(p, "seed", -1)
            original = image.convert("RGB")

            if save_originals:
                original.save(os.path.join(self._neo_outdir_orig, f"{timestamp}_{base_seed}_{idx:03}_original.png"))

            processed_img = original.copy()
            for effect_type, strength in pipeline:
                processed_img = self.apply_effect(processed_img, effect_type, strength)
                if not isinstance(processed_img, Image.Image):
                    processed_img = Image.fromarray(np.asarray(processed_img).astype(np.uint8))
                processed_img = processed_img.convert("RGB")

            if save_processed:
                tag = "_".join(e.replace(" ", "") for e, _ in pipeline)[:180]
                processed_img.save(os.path.join(self._neo_outdir_processed, f"{timestamp}_{base_seed}_{idx:03}_{tag}.png"))

            # UI 上直接显示处理结果；开启对比时显示左右原图/处理图。
            if show_compare:
                combined = Image.new("RGB", (original.width * 2, original.height))
                combined.paste(original, (0, 0))
                combined.paste(processed_img, (original.width, 0))
                pp.image = combined
            else:
                pp.image = processed_img

            print(f"🐱 MIAOKA Neo: image {idx + 1} 已处理 | " + " → ".join(f"{e} {s:.0f}%" for e, s in pipeline))
        except Exception as e:
            print(f"❌ 喵咔 Neo 后处理失败: {e}")

    def postprocess(self, p, processed, effect_select, *args):
        """兼容部分 Forge/A1111 分支；Neo 主路径由 postprocess_image() 完成。"""
        if IS_FORGE:
            return
        self._process_from_args(p, processed, effect_select, args)

    def _neo_prepare_output_dirs(self, p, save_originals, save_processed):
        if hasattr(self, "_neo_dirs_ready"):
            return
        base_outdir = getattr(p, "outpath_samples", None) or "outputs"
        self._neo_outdir_orig = os.path.join(base_outdir, "original")
        self._neo_outdir_processed = os.path.join(base_outdir, "processed")
        if save_originals:
            os.makedirs(self._neo_outdir_orig, exist_ok=True)
        if save_processed:
            os.makedirs(self._neo_outdir_processed, exist_ok=True)
        self._neo_timestamp = time.strftime("%Y%m%d_%H%M%S")
        self._neo_image_index = 0
        self._neo_dirs_ready = True

    def _process_from_args(self, p, result, effect_select, args):
        """解析 UI 参数并运行可叠加后处理管线。"""
        n = len(getattr(self, "effect_names", [])) or 39
        strengths = list(args[:n])
        rest = list(args[n:])
        strengths += [0] * max(0, n - len(strengths))
        apply_to = rest[0] if len(rest) > 0 else "所有图像"
        show_compare = rest[1] if len(rest) > 1 else True
        save_originals = rest[2] if len(rest) > 2 else True
        save_processed = rest[3] if len(rest) > 3 else True
        selected = set(effect_select or [])
        pipeline = [(name, float(strengths[i] or 0)) for i, name in enumerate(self.effect_names)
                    if name in selected and float(strengths[i] or 0) > 0]
        return self._process_result(p, result, pipeline, apply_to, show_compare, save_originals, save_processed)

    def _process_result(self, p, result, pipeline, apply_to, show_compare, save_originals, save_processed):
        if not pipeline:
            return result
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        base_outdir = getattr(p, "outpath_samples", None) or "outputs"
        outdir_orig = os.path.join(base_outdir, "original")
        outdir_processed = os.path.join(base_outdir, "processed")
        if save_originals: os.makedirs(outdir_orig, exist_ok=True)
        if save_processed: os.makedirs(outdir_processed, exist_ok=True)
        processed_images, combined_images = [], []
        images = list(getattr(result, "images", []) or [])
        base_seed = getattr(result, "seed", getattr(p, "seed", -1))
        for i, img in enumerate(images):
            try:
                if not isinstance(img, Image.Image):
                    if isinstance(img, np.ndarray): img = Image.fromarray(img)
                    else: processed_images.append(img); continue
                if save_originals:
                    img.save(os.path.join(outdir_orig, f"{timestamp}_{base_seed}_{i:03}_original.png"))
                if apply_to == "仅第一张" and i > 0:
                    processed_images.append(img); continue
                processed_img = img.convert("RGB")
                for effect_type, strength in pipeline:
                    processed_img = self.apply_effect(processed_img, effect_type, strength)
                processed_images.append(processed_img)
                if save_processed:
                    tag = "_".join(e.replace(" ", "") for e, _ in pipeline)[:180]
                    processed_img.save(os.path.join(outdir_processed, f"{timestamp}_{base_seed}_{i:03}_{tag}.png"))
                if show_compare:
                    combined = Image.new("RGB", (img.width * 2, img.height))
                    combined.paste(img.convert("RGB"), (0, 0)); combined.paste(processed_img.convert("RGB"), (img.width, 0))
                    combined_images.append(combined)
            except Exception as e:
                print(f"❌ 喵咔图像处理失败 (image {i}): {e}")
                processed_images.append(img)
        result.images = processed_images + combined_images if show_compare and combined_images else processed_images
        print(f"\n🐱 MIAOKA 已处理 {len(processed_images)} 张图像 | 管线: " + " → ".join(f"{e} {s:.0f}%" for e,s in pipeline))
        if IS_FORGE: print("🔧 Forge Classic / Neo: postprocess()")
        return result

    def apply_effect(self, image, effect_type, strength):
        """旧效果 + MIAOKA 新增效果。"""
        if image.mode != "RGB": image = image.convert("RGB")
        # 原有 16 项
        old = {
            "高斯噪点 Gaussian Noise": self.add_gaussian_noise, "椒盐噪点 Salt & Pepper Noise": self.add_salt_pepper_noise,
            "均匀噪点 Uniform Noise": self.add_uniform_noise, "斑点噪点 Speckle Noise": self.add_speckle_noise,
            "高斯模糊 Gaussian Blur": self.apply_gaussian_blur, "运动模糊 Motion Blur": self.apply_motion_blur,
            "锐化 Sharpen": self.apply_sharpen, "边缘检测 Edge Detection": self.apply_edge_detection,
            "油画效果 Oil Painting": self.apply_oil_painting, "铅笔画 Pencil Sketch": self.apply_pencil_sketch,
            "怀旧棕调 Sepia": self.apply_sepia, "像素化 Pixelate": self.apply_pixelate,
            "雨滴效果 Rain Drops": self.apply_rain_effect, "胶片颗粒 Film Grain": self.apply_film_grain,
            "素描效果 Sketch": self.apply_sketch
        }
        if effect_type in old:
            return old[effect_type](image, strength)
        if effect_type == "反色 Invert": return ImageOps.blend(image, ImageOps.invert(image), min(1, strength/100))
        funcs = {
            "曝光 Exposure": self.apply_exposure, "亮度 Brightness": self.apply_brightness, "对比度 Contrast": self.apply_contrast,
            "饱和度 Saturation": self.apply_saturation, "鲜艳度 Vibrance": self.apply_vibrance, "色温 Temperature": self.apply_temperature,
            "色调 Tint": self.apply_tint, "高光 Highlights": self.apply_highlights, "阴影 Shadows": self.apply_shadows,
            "清晰度 Clarity": self.apply_clarity, "智能锐化 Smart Sharpen": self.apply_smart_sharpen,
            "局部对比度 Local Contrast": self.apply_local_contrast, "边缘保护降噪 Edge-Preserving Denoise": self.apply_edge_denoise,
            "光晕 Bloom": self.apply_bloom, "柔光 Soft Light": self.apply_soft_light, "暗角 Vignette": self.apply_vignette,
            "褪色 Fade": self.apply_fade, "色彩平衡 Color Balance": self.apply_color_balance, "电影色调 Cinematic Tone": self.apply_cinematic,
            "HDR 高动态范围": self.apply_hdr, "景深柔化 Depth Softening": self.apply_depth_soften, "镜头模糊 Lens Blur": self.apply_lens_blur,
            "色差 Chromatic Aberration": self.apply_chromatic_aberration, "RGB 分离 RGB Split": self.apply_rgb_split
        }
        return funcs.get(effect_type, lambda im, st: im)(image, strength)

    # =================== 新增 MIAOKA 后处理 ===================
    def _blend(self, a, b, amount):
        return Image.blend(a.convert("RGB"), b.convert("RGB"), float(np.clip(amount,0,1)))

    def apply_exposure(self, image, s):
        if not CV2_AVAILABLE: return image
        factor = 2.0 ** ((s - 50) / 25.0) if s != 0 else 1.0
        return self._blend(image, Image.fromarray(np.clip(np.array(image).astype(np.float32)*factor,0,255).astype(np.uint8)), min(1,s/100))
    def apply_brightness(self, image, s):
        from PIL import ImageEnhance
        return ImageEnhance.Brightness(image).enhance(1 + s/200)
    def apply_contrast(self, image, s):
        from PIL import ImageEnhance
        return ImageEnhance.Contrast(image).enhance(1 + s/150)
    def apply_saturation(self, image, s):
        from PIL import ImageEnhance
        return ImageEnhance.Color(image).enhance(1 + s/120)
    def apply_vibrance(self, image, s):
        arr=np.asarray(image).astype(np.float32)/255; mx=arr.max(2); mn=arr.min(2); sat=(mx-mn)/(mx+1e-6); amount=(s/100)*(1-sat); gray=arr.mean(2,keepdims=True); out=gray+(arr-gray)*(1+amount[...,None]); return Image.fromarray(np.clip(out*255,0,255).astype(np.uint8))
    def apply_temperature(self, image, s):
        arr=np.asarray(image).astype(np.float32); t=(s/100)*22; arr[:,:,0]+=t; arr[:,:,2]-=t; return Image.fromarray(np.clip(arr,0,255).astype(np.uint8))
    def apply_tint(self, image, s):
        arr=np.asarray(image).astype(np.float32); t=(s/100)*18; arr[:,:,1]+=t; arr[:,:,0]-=t*0.35; arr[:,:,2]-=t*0.35; return Image.fromarray(np.clip(arr,0,255).astype(np.uint8))
    def apply_highlights(self, image, s):
        arr=np.asarray(image).astype(np.float32)/255; lum=arr.mean(2,keepdims=True); mask=np.clip((lum-.55)/.45,0,1); out=arr*(1-(s/100)*.22*mask); return Image.fromarray(np.clip(out*255,0,255).astype(np.uint8))
    def apply_shadows(self, image, s):
        arr=np.asarray(image).astype(np.float32)/255; lum=arr.mean(2,keepdims=True); mask=np.clip((.55-lum)/.55,0,1); out=arr+(1-arr)*(s/100)*.18*mask; return Image.fromarray(np.clip(out*255,0,255).astype(np.uint8))
    def apply_clarity(self, image, s):
        if CV2_AVAILABLE:
            a=np.asarray(image); blur=cv2.GaussianBlur(a,(0,0),max(.6,1.2+s/35)); high=a.astype(np.float32)-blur.astype(np.float32); out=a.astype(np.float32)+high*(s/100)*1.15; return Image.fromarray(np.clip(out,0,255).astype(np.uint8))
        return self.apply_sharpen(image,s*.7)
    def apply_smart_sharpen(self, image, s):
        if CV2_AVAILABLE:
            a=np.asarray(image); blur=cv2.GaussianBlur(a,(0,0),1.0); detail=a.astype(np.float32)-blur.astype(np.float32); out=a.astype(np.float32)+detail*(s/100)*.8; return Image.fromarray(np.clip(out,0,255).astype(np.uint8))
        return self.apply_sharpen(image,s*.7)
    def apply_local_contrast(self, image, s):
        if not CV2_AVAILABLE: return self.apply_contrast(image,s*.5)
        lab=cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2LAB); l,a,b=cv2.split(lab); clahe=cv2.createCLAHE(clipLimit=1+2*s/100,tileGridSize=(8,8)); out=cv2.cvtColor(cv2.merge((clahe.apply(l),a,b)),cv2.COLOR_LAB2RGB); return self._blend(image,Image.fromarray(out),s/100)
    def apply_edge_denoise(self, image, s):
        if CV2_AVAILABLE:
            a=np.asarray(image); smooth=cv2.bilateralFilter(a,7,20+80*s/100,20+80*s/100); return self._blend(image,Image.fromarray(smooth),s/100)
        return image.filter(ImageFilter.SMOOTH)
    def apply_bloom(self, image, s):
        a=np.asarray(image).astype(np.float32); lum=a.mean(2); mask=np.clip((lum-170)/85,0,1); glow=Image.fromarray((a*mask[...,None]).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3+s/10)); return Image.blend(image,Image.fromarray(np.clip(a+np.asarray(glow)*.55,0,255).astype(np.uint8)),s/100)
    def apply_soft_light(self, image, s):
        blur=image.filter(ImageFilter.GaussianBlur(2+s/20)); return self._blend(image,Image.blend(image,blur,.5),s/100)
    def apply_vignette(self, image, s):
        h,w=image.height,image.width; y,x=np.ogrid[:h,:w]; cx,cy=w/2,h/2; d=np.sqrt(((x-cx)/cx)**2+((y-cy)/cy)**2); mask=np.clip((d-.25)/.9,0,1); arr=np.asarray(image).astype(np.float32)*(1-mask[...,None]*(s/100)*.48); return Image.fromarray(np.clip(arr,0,255).astype(np.uint8))
    def apply_fade(self, image, s):
        arr=np.asarray(image).astype(np.float32); arr=arr*.92+128*.08; return self._blend(image,Image.fromarray(np.clip(arr,0,255).astype(np.uint8)),s/100)
    def apply_color_balance(self, image, s):
        arr=np.asarray(image).astype(np.float32); amt=s/100*18; arr[:,:,0]+=amt; arr[:,:,2]-=amt*.65; return Image.fromarray(np.clip(arr,0,255).astype(np.uint8))
    def apply_cinematic(self, image, s):
        arr=np.asarray(image).astype(np.float32)/255; lum=arr.mean(2,keepdims=True); arr[:,:,0]+=(.04*s/100)*(1-lum[:,:,0]); arr[:,:,2]+=(.035*s/100)*lum[:,:,0]; arr=np.clip((arr-.5)*(1+.12*s/100)+.5,0,1); return Image.fromarray((arr*255).astype(np.uint8))
    def apply_hdr(self, image, s):
        if not CV2_AVAILABLE: return self.apply_clarity(image,s*.5)
        a=np.asarray(image); lab=cv2.cvtColor(a,cv2.COLOR_RGB2LAB); l,aa,bb=cv2.split(lab); clahe=cv2.createCLAHE(clipLimit=1+3*s/100,tileGridSize=(8,8)); out=cv2.cvtColor(cv2.merge((clahe.apply(l),aa,bb)),cv2.COLOR_LAB2RGB); return self._blend(image,Image.fromarray(out),s*.55/100)
    def apply_depth_soften(self, image, s):
        # 无深度模型时采用中心保护的渐变模糊，避免额外 AI 模型依赖。
        blur=image.filter(ImageFilter.GaussianBlur(1+s/8)); h,w=image.height,image.width; y,x=np.ogrid[:h,:w]; d=np.sqrt(((x-w/2)/(w/2))**2+((y-h/2)/(h/2))**2); mask=np.clip((d-.25)/.75,0,1)*s/100; return Image.fromarray((np.asarray(image)*(1-mask[...,None])+np.asarray(blur)*mask[...,None]).astype(np.uint8))
    def apply_lens_blur(self, image, s):
        return self._blend(image,image.filter(ImageFilter.GaussianBlur(.3+s/18)),s/100)
    def apply_chromatic_aberration(self, image, s):
        a=np.asarray(image); shift=max(1,int(1+s/18)); out=a.copy(); out[:,:,0]=np.roll(a[:,:,0],shift,1); out[:,:,2]=np.roll(a[:,:,2],-shift,1); return self._blend(image,Image.fromarray(out),s/100)
    def apply_rgb_split(self, image, s):
        a=np.asarray(image); shift=max(1,int(1+s/15)); out=a.copy(); out[:,:,0]=np.roll(a[:,:,0],shift,1); out[:,:,2]=np.roll(a[:,:,2],-shift,1); return self._blend(image,Image.fromarray(out),min(1,s/70))

    # =================== 喵咔图像处理效果 ===================
    # 噪点效果
    def add_gaussian_noise(self, image, strength):
        """添加高斯噪点 Gaussian Noise (喵咔 MIAOKA)"""
        img_array = np.array(image).astype(np.float32) / 255.0
        noise = np.random.normal(0, strength / 100.0, img_array.shape)
        noisy_array = np.clip(img_array + noise, 0, 1) * 255
        return Image.fromarray(noisy_array.astype(np.uint8))
    
    def add_salt_pepper_noise(self, image, strength):
        """添加椒盐噪点 Salt & Pepper Noise (喵咔 MIAOKA)"""
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
        """添加均匀噪点 Uniform Noise (喵咔 MIAOKA)"""
        img_array = np.array(image).astype(np.float32) / 255.0
        noise = np.random.uniform(-strength / 100.0, strength / 100.0, img_array.shape)
        noisy_array = np.clip(img_array + noise, 0, 1) * 255
        return Image.fromarray(noisy_array.astype(np.uint8))
    
    def add_speckle_noise(self, image, strength):
        """添加斑点噪点 Speckle Noise (喵咔 MIAOKA)"""
        img_array = np.array(image).astype(np.float32) / 255.0
        noise = np.random.randn(*img_array.shape) * (strength / 100.0)
        noisy_array = np.clip(img_array + img_array * noise, 0, 1) * 255
        return Image.fromarray(noisy_array.astype(np.uint8))
    
    # 滤镜效果
    def apply_gaussian_blur(self, image, strength):
        """应用高斯模糊 Gaussian Blur (喵咔 MIAOKA)"""
        radius = max(0.5, strength / 20)
        return image.filter(ImageFilter.GaussianBlur(radius=radius))
    
    def apply_motion_blur(self, image, strength):
        """应用运动模糊 Motion Blur (喵咔 MIAOKA)"""
        if not CV2_AVAILABLE:
            print("⚠️ 喵咔: 运动模糊 Motion Blur需要OpenCV，使用高斯模糊 Gaussian Blur代替")
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
            print(f"⚠️ 喵咔: 运动模糊 Motion Blur失败: {e}")
            return image
    
    def apply_sharpen(self, image, strength):
        """应用锐化 Sharpen (喵咔 MIAOKA)"""
        return image.filter(ImageFilter.UnsharpMask(radius=2, percent=strength, threshold=3))
    
    def apply_edge_detection(self, image, strength):
        """应用边缘检测 Edge Detection (喵咔 MIAOKA)"""
        if not CV2_AVAILABLE:
            print("⚠️ 喵咔: 边缘检测 Edge Detection需要OpenCV，使用Sobel滤镜代替")
            return image.filter(ImageFilter.FIND_EDGES)
        
        try:
            img_array = np.array(image)
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            edges = cv2.Canny(gray, strength, strength * 2)
            return Image.fromarray(edges)
        except Exception as e:
            print(f"⚠️ 喵咔: 边缘检测 Edge Detection失败: {e}")
            return image
    
    def apply_oil_painting(self, image, strength):
        """应用油画效果 Oil Painting (喵咔 MIAOKA)"""
        if not CV2_AVAILABLE:
            print("⚠️ 喵咔: 油画效果 Oil Painting需要OpenCV，使用海报化代替")
            return image.filter(ImageFilter.MedianFilter(size=3))
        
        try:
            img_array = np.array(image)
            size = max(1, int(strength / 20))
            oil = cv2.xphoto.oilPainting(img_array, size=size, dynRatio=1)
            return Image.fromarray(oil)
        except Exception as e:
            print(f"⚠️ 喵咔: 油画效果 Oil Painting失败: {e}")
            return image
    
    def apply_pencil_sketch(self, image, strength):
        """应用铅笔画 Pencil Sketch效果 (喵咔 MIAOKA)"""
        if not CV2_AVAILABLE:
            print("⚠️ 喵咔: 铅笔画 Pencil Sketch效果需要OpenCV，使用轮廓滤镜代替")
            return image.filter(ImageFilter.CONTOUR)
        
        try:
            img_array = np.array(image)
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            inverted = 255 - gray
            blurred = cv2.GaussianBlur(inverted, (21, 21), 0)
            pencil = cv2.divide(gray, 255 - blurred, scale=256)
            return Image.fromarray(pencil)
        except Exception as e:
            print(f"⚠️ 喵咔: 铅笔画 Pencil Sketch效果失败: {e}")
            return image
    
    def apply_sepia(self, image, strength):
        """应用怀旧棕调 Sepia (喵咔 MIAOKA)"""
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
        """应用反色 Invert (喵咔 MIAOKA)"""
        return ImageOps.invert(image)
    
    def apply_pixelate(self, image, strength):
        """应用像素化 Pixelate (喵咔 MIAOKA)"""
        size = max(1, int(strength / 10))
        small = image.resize((image.width // size, image.height // size), Image.NEAREST)
        return small.resize(image.size, Image.NEAREST)
    
    def apply_rain_effect(self, image, strength):
        """应用雨滴效果 Rain Drops (喵咔 MIAOKA)"""
        if not CV2_AVAILABLE:
            print("⚠️ 喵咔: 雨滴效果 Rain Drops需要OpenCV，跳过效果")
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
            print(f"⚠️ 喵咔: 雨滴效果 Rain Drops失败: {e}")
            return image
    
    def apply_film_grain(self, image, strength):
        """应用胶片颗粒 Film Grain效果 (喵咔 MIAOKA)"""
        img_array = np.array(image).astype(np.float32) / 255.0
        noise = np.random.normal(0, strength / 200.0, img_array.shape)
        noisy_array = np.clip(img_array + noise, 0, 1) * 255
        result = Image.fromarray(noisy_array.astype(np.uint8))
        return result.filter(ImageFilter.GaussianBlur(radius=0.5))
    
    def apply_sketch(self, image, strength):
        """应用素描效果 Sketch (喵咔 MIAOKA)"""
        if not CV2_AVAILABLE:
            print("⚠️ 喵咔: 素描效果 Sketch需要OpenCV，使用轮廓滤镜代替")
            return image.filter(ImageFilter.CONTOUR)
        
        try:
            img_array = np.array(image)
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            inverted = 255 - gray
            blurred = cv2.GaussianBlur(inverted, (21, 21), 0)
            sketch = cv2.divide(gray, 255 - blurred, scale=256)
            return Image.fromarray(sketch).convert("RGB")
        except Exception as e:
            print(f"⚠️ 喵咔: 素描效果 Sketch失败: {e}")
            return image
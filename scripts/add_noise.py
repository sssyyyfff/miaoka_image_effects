import os
import time
import numpy as np
from PIL import Image
import gradio as gr
import modules.scripts as scripts
from modules.processing import StableDiffusionProcessing, process_images
from modules import shared

class Script(scripts.Script):
    def title(self):
        return "Add Noise to Output (by MIAOKA)"

    def show(self, is_img2img):
        return True  # 显示在 txt2img 和 img2img 页面中

    def ui(self, is_img2img):
        with gr.Row():
            noise_strength = gr.Slider(
                minimum=0,
                maximum=100,
                step=1,
                label="噪点强度 (%)",
                value=10,
            )
            noise_type = gr.Dropdown(
                choices=[
                    "Gaussian（高斯噪点）",
                    "Salt and Pepper（椒盐噪点）",
                    "Poisson（泊松噪点）",
                    "Uniform（均匀噪点）",
                    "Speckle（斑点噪点）"
                ],
                label="噪点类型",
                value="Gaussian（高斯噪点）"
            )
        with gr.Row():
            apply_to = gr.Radio(
                choices=["所有图像", "仅第一张"],
                label="加噪图像范围",
                value="所有图像",
            )
        with gr.Row():
            preset_btn = gr.Button("轻微 (5%)")
            preset_btn_2 = gr.Button("中等 (15%)")
            preset_btn_3 = gr.Button("强烈 (30%)")

        with gr.Row():
            show_compare = gr.Checkbox(label="显示对比图", value=True)

        def set_preset(val):
            return gr.update(value=val)

        preset_btn.click(fn=lambda: set_preset(5), outputs=noise_strength)
        preset_btn_2.click(fn=lambda: set_preset(15), outputs=noise_strength)
        preset_btn_3.click(fn=lambda: set_preset(30), outputs=noise_strength)

        return [noise_strength, noise_type, apply_to, show_compare]

    def run(self, p: StableDiffusionProcessing, noise_strength, noise_type, apply_to, show_compare):
        result = process_images(p)

        base_outdir = p.outpath_samples
        outdir_orig = os.path.join(base_outdir, "original")
        outdir_noised = os.path.join(base_outdir, "noised")

        os.makedirs(outdir_orig, exist_ok=True)
        os.makedirs(outdir_noised, exist_ok=True)

        combined_images = []
        timestamp = time.strftime("%Y%m%d_%H%M%S")

        for i, img in enumerate(result.images):
            try:
                orig_path = os.path.join(outdir_orig, f"{timestamp}_original_{i:03}.png")
                img.save(orig_path)

                if apply_to == "仅第一张" and i > 0:
                    continue

                if img.mode != "RGB":
                    img = img.convert("RGB")
                img_array = np.array(img).astype(np.float32)

                # 生成噪点图像
                noisy_array = self.add_noise(img_array, noise_type, noise_strength)

                noisy_image = Image.fromarray(np.uint8(np.clip(noisy_array, 0, 255)))
                result.images[i] = noisy_image

                noise_path = os.path.join(outdir_noised, f"{timestamp}_noised_{i:03}.png")
                noisy_image.save(noise_path)

                if show_compare:
                    combined = Image.new("RGB", (img.width * 2, img.height))
                    combined.paste(img, (0, 0))
                    combined.paste(noisy_image, (img.width, 0))
                    combined_images.append(combined)

            except Exception as e:
                print(f"❌ 加噪失败 image {i}: {e}")
                continue

        if show_compare:
            result.images.extend(combined_images)

        return result

    def add_noise(self, image, noise_type, strength):
        # 所有噪点算法都在 0~1 范围内进行处理
        image = image / 255.0

        if "Gaussian" in noise_type:
            # 高斯噪点：模拟真实相机的随机扰动
            noise = np.random.normal(0, strength / 100.0, image.shape)
            return (image + noise) * 255

        elif "Salt and Pepper" in noise_type:
            # 椒盐噪点：像素变成纯黑或纯白，模拟老旧图像的损坏
            output = np.copy(image)
            prob = strength / 500.0
            rand = np.random.rand(*image.shape[:2])
            salt = rand < prob
            pepper = rand > 1 - prob
            if image.ndim == 3:
                output[salt] = 1
                output[pepper] = 0
            else:
                output[salt] = 1
                output[pepper] = 0
            return output * 255

        elif "Poisson" in noise_type:
            # 泊松噪点：根据图像亮度自然生成，更符合光学系统（例如弱光拍摄）
            vals = len(np.unique(image))
            vals = 2 ** np.ceil(np.log2(vals))
            noisy = np.random.poisson(image * vals) / float(vals)
            return noisy * 255

        elif "Uniform" in noise_type:
            # 均匀噪点：每个像素都被加上一个固定范围内的随机值
            noise = np.random.uniform(-strength / 100.0, strength / 100.0, image.shape)
            return (image + noise) * 255

        elif "Speckle" in noise_type:
            # 斑点噪点：图像 * (1 + 噪声)，常见于老照片的“腐蚀点”效果
            noise = np.random.randn(*image.shape) * (strength / 100.0)
            return (image + image * noise) * 255

        else:
            # 默认不添加噪点
            return image * 255

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
        return not is_img2img

    def ui(self, is_img2img):
        with gr.Row():
            noise_strength = gr.Slider(
                minimum=0,
                maximum=100,
                step=1,
                label="Noise Strength (%)",
                value=10,
            )
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

        return [noise_strength, apply_to, show_compare]

    def run(self, p: StableDiffusionProcessing, noise_strength, apply_to, show_compare):
        result = process_images(p)

        base_outdir = p.outpath_samples  # 当前生成任务文件夹
        outdir_orig = os.path.join(base_outdir, "original")
        outdir_noised = os.path.join(base_outdir, "noised")

        os.makedirs(outdir_orig, exist_ok=True)
        os.makedirs(outdir_noised, exist_ok=True)

        combined_images = []

        timestamp = time.strftime("%Y%m%d_%H%M%S")

        for i, img in enumerate(result.images):
            try:
                # 文件名带时间戳避免重名
                orig_path = os.path.join(outdir_orig, f"{timestamp}_original_{i:03}.png")
                img.save(orig_path)

                if apply_to == "仅第一张" and i > 0:
                    continue

                if img.mode != "RGB":
                    img = img.convert("RGB")

                img_array = np.array(img).astype(np.float32)
                if img_array.ndim != 3 or img_array.shape[2] != 3:
                    print(f"⚠️ 跳过图像 {i}: 非 RGB 图像")
                    continue

                noise_std = noise_strength / 100.0 * 50
                noise = np.random.normal(0, noise_std, img_array.shape).astype(np.float32)
                noisy_array = np.clip(img_array + noise, 0, 255).astype(np.uint8)
                noisy_image = Image.fromarray(noisy_array)

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

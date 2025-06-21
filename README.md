# Add Noise to Output (by MIAOKA)

This is an extension for AUTOMATIC1111's Stable Diffusion Web UI that adds adjustable Gaussian noise to images generated via txt2img.

- ✍️ Author: MIAOKA
- 📦 Version: 1.0
- 🧪 Feature: Adds post-processing Gaussian noise
- 🎯 Scope: Only applies to txt2img output (not img2img)

---

## 中文简介

这是一个为 AUTOMATIC1111 的 Stable Diffusion WebUI 制作的扩展，由 **MIAOKA** 编写。

它可以在文生图（txt2img）流程中，为最终生成的图像添加 **可调节强度的高斯噪点**，增强图像质感或用于训练数据增强。

---

## 使用方法（Usage）

1. 将本扩展放入 WebUI 的 `extensions/` 目录，例如：

2. 重启 WebUI。

3. 打开 `txt2img` 页面，在底部找到：

4. 调整 “Noise Strength (%)” 滑条，例如设置为 `10%`。

5. 输入提示词并生成图像，图像将自动添加噪点。

---

## 示例（Example）

| 原始图像 | 加噪图像 (30%) |
|----------|----------------|
| ![original](examplessd_add_noise/original.png) | ![noisy](sd_add_noise/noised.png) |

*（请根据实际项目添加示例图）*

---

## 版权声明

版权所有 © MIAOKA  
本扩展仅供学习和个人使用，禁止用于商业用途。若需转载或修改，请联系作者。


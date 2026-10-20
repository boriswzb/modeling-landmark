"""Generate a seamless equirectangular golden-hour desert sky."""
import numpy as np
from PIL import Image, ImageFilter
import os

W, H = 2048, 1024
v = np.linspace(0, 1, H, dtype=np.float32)[:, None]
u = np.linspace(0, 1, W, dtype=np.float32)[None, :]
e = np.clip((0.5 - v) * 2.0, 0, 1)  # 0 at horizon, 1 at zenith

horizon = np.array([1.0, 0.80, 0.58], np.float32)
mid = np.array([0.48, 0.68, 0.94], np.float32)
zenith = np.array([0.10, 0.28, 0.62], np.float32)

t1 = np.clip(e / 0.040, 0, 1)[..., None]
t2 = np.clip((e - 0.020) / 0.20, 0, 1)[..., None]
rgb = horizon * (1 - t1) + mid * t1
rgb = rgb * (1 - t2) + zenith * t2
rgb = np.broadcast_to(rgb, (H, W, 3)).copy()

# warm, luminous dust band just above the horizon
band = np.exp(-((e - 0.035) / 0.035) ** 2)[..., None]
rgb = rgb * (1 - 0.45 * band) + np.array([1.0, 0.72, 0.45], np.float32)[None, None, :] * (0.45 * band)

# very faint high cirrus, stretched horizontally
rng = np.random.default_rng(77)
small = rng.random((64, 128), dtype=np.float32)
from PIL import Image as I
cloud = I.fromarray((small * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(8))
cloud = np.asarray(cloud, np.float32) / 255.0
cloud *= np.clip((e - 0.18) / 0.4, 0, 1) * 0.10
rgb += (cloud[..., None] - 0.05) * np.array([0.9, 0.8, 0.7], np.float32)[None, None, :]

# soft sun glow behind the camera's left shoulder (south-west)
az = np.linspace(0, 2 * np.pi, W, endpoint=False, dtype=np.float32)[None, :]
el = (0.5 - v) * np.pi
sun_az, sun_el = np.radians(115.0), np.radians(12.0)
cosang = np.sin(el) * np.sin(sun_el) + np.cos(el) * np.cos(sun_el) * np.cos(az - sun_az)
ang = np.arccos(np.clip(cosang, -1, 1))
glow = np.exp(-(ang / 0.22) ** 2)[..., None]
rgb += glow * np.array([0.45, 0.26, 0.10], np.float32)[None, None, :]

rgb = np.clip(rgb, 0, 1)
# image is stored in sRGB
rgb = np.where(rgb <= 0.0031308, 12.92 * rgb, 1.055 * np.power(rgb, 1 / 2.4) - 0.055)
img = Image.fromarray((rgb * 255).astype(np.uint8), "RGB")
img.save(os.path.join(os.path.dirname(__file__), "textures", "sky_golden.png"), optimize=True)
print("saved sky_golden.png")

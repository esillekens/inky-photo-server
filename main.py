import numpy as np
import cv2
import matplotlib.pyplot as plt
from PIL import Image
from scipy.optimize import minimize
from dither_engine import dither_to_indexed, apply_adjustments, get_palette_list


import time

# --- Configuration ---
target_size = (640, 400)
colours = np.array([
    [0., 0., 0.],       # black
    [100., 0., 0.],     # white
    [25., -100., 0.],   # green
    [25., 50., -86.],   # blue
    [50., 81., 59.],    # red
    [100., 0, 100.],    # yellow
    [75., 50., 86.],    # orange
], dtype='float32')

# Load and Correct Rotation
img = cv2.imread('romance-trein.jpg')
img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

# Fix: Use cv2.rotate instead of swapaxes to avoid mirroring
if img.shape[1] < img.shape[0]:
    img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)

# Resize & Crop Logic
h, w = img.shape[:2]
aspect_target = target_size[0] / target_size[1]
aspect_img = w / h

if aspect_img > aspect_target:
    new_w = int(h * aspect_target)
    start_x = (w - new_w) // 2
    img = img[:, start_x:start_x+new_w]
else:
    new_h = int(w / aspect_target)
    start_y = (h - new_h) // 2
    img = img[start_y:start_y+new_h, :]

img = cv2.resize(img, target_size, interpolation=cv2.INTER_LANCZOS4)
img_lab = cv2.cvtColor(img.astype(np.float32)/255, cv2.COLOR_RGB2LAB)

# --- Optimization ---
def calculate_hue_loss(params, source, palette):
    adj = apply_adjustments(source, *params)
    pix = adj.reshape(-1, 3)
    diff = pix[:, np.newaxis, :] - palette[np.newaxis, :, :]
    dists = np.sum(diff**2, axis=2)
    nearest = palette[np.argmin(dists, axis=1)]
    return np.mean(np.sum((nearest - source.reshape(-1, 3))**2, axis=1))

print("Optimizing...")
tic = time.perf_counter()
res = minimize(calculate_hue_loss, [1.1, 0.5, 0.0, 100.0, 1.0, 1.0, 0.0],
               args=(img_lab, colours), method='Nelder-Mead', options={'maxiter': 400},
               bounds=[(0.5,3),(0,2),(-20,40),(60,150),(0.4,2.2),(0.8,3),(-0.2,0.2)])

# Apply Results
best_params = dict(zip(['sat', 'vibrance', 'blk', 'wht', 'gam', 'contrast', 'hue_rot'], res.x))
img_adj = apply_adjustments(img_lab, **best_params)
toc = time.perf_counter()
print(f"Optimisation in {toc - tic:0.4f} seconds")

# Dither
print("Dithering...")
tic = time.perf_counter()
img_idx = dither_to_indexed(img_adj, colours, c=0.013*2)
toc = time.perf_counter()
print(f"Dithering in {toc - tic:0.4f} seconds")

# Save proper P-mode image
raw_image = Image.fromarray(img_idx, mode='P')
raw_image.putpalette(get_palette_list(colours))
raw_image.save('raw_image.png')

# Show previews
plt.figure("Adjusted LAB")
plt.imshow(cv2.cvtColor(img_adj, cv2.COLOR_LAB2RGB))
plt.figure("Final Dither")
plt.imshow(cv2.cvtColor(colours[img_idx].astype('float32'), cv2.COLOR_LAB2RGB))
plt.show()
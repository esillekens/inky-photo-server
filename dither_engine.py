import numpy as np
import cv2

from numba import jit

@jit(nopython=True)
def dither_to_indexed(img_lab, palette, c=0.5):
    height, width = img_lab.shape[:2]
    index_map = np.zeros((height, width), dtype=np.uint8)
    
    # Zhang-Pan spatial weight matrix
    w = np.array([[0.1035, 0.1465, 0.1035],
                  [0.1465, 0.0,    0.1465],
                  [0.1035, 0.1465, 0.1035]])

    kernel = np.array([
        [1, 0, 7/16],
        [-1, 1, 3/16],
        [0, 1, 5/16],
        [1, 1, 1/16]
    ])

    work_img = img_lab.copy()

    for y in range(height):
        for x in range(width):
            old_pixel = work_img[y, x]
            
            # Structure Awareness
            itf = 0.0
            if 0 < x < width - 1 and 0 < y < height - 1:
                window = work_img[y-1:y+2, x-1:x+2, 0]
                avg_l = np.mean(window)
                vis_err = window - avg_l
                spatial_var = np.sum(w * np.abs(vis_err))
                activity = spatial_var * (work_img[y, x, 0] - avg_l)
                itf = c * (avg_l / 100.0) * activity
                itf = max(-20.0, min(20.0, itf))

            test_pixel = old_pixel.copy()
            test_pixel[0] += itf 

            # Find Best Index
            diff = test_pixel - palette
            # Weighted LAB distance
            dist = (diff[:,0]**2) + (diff[:,1]**2 * 1.5) + (diff[:,2]**2 * 1.5)
            chosen_idx = np.argmin(dist)
            
            index_map[y, x] = chosen_idx
            err = old_pixel - palette[chosen_idx]

            # Error Diffusion
            for dx_k, dy_k, weight in kernel:
                xn, yn = x + int(dx_k), y + int(dy_k)
                if 0 <= xn < width and 0 <= yn < height:
                    work_img[yn, xn] += err * weight

    return index_map

def apply_adjustments(img_lab_input, sat=1.0, vibrance=0.0, blk=0.0, wht=100.0, gam=1.0, contrast=1.0, hue_rot=0.0):
    l, a, b = cv2.split(img_lab_input)
    l = (l - blk) * (100.0 / max(wht - blk, 1.0))
    
    l_norm = (l - 50.0) / 50.0
    l = np.tanh(contrast * l_norm) * 50.0 + 50.0
    
    l = np.clip(l / 100.0, 0.0, 1.0)
    l = np.power(l, 1.0 / gam) * 100.0
    
    cos_r, sin_r = np.cos(hue_rot), np.sin(hue_rot)
    a_new = a * cos_r - b * sin_r
    b_new = a * sin_r + b * cos_r
    
    sat_mag = np.sqrt(a_new**2 + b_new**2)
    k, center = 0.1, 50.0
    vibe_sigmoid = 1.0 / (1.0 + np.exp(k * (sat_mag - center)))
    vibe_mask = 1.0 + (vibrance * vibe_sigmoid)
    
    a_final = np.clip(a_new * sat * vibe_mask, -127, 127)
    b_final = np.clip(b_new * sat * vibe_mask, -127, 127)
    l_final = np.clip(l, 0, 100)
    
    return cv2.merge([l_final.astype(np.float32), a_final.astype(np.float32), b_final.astype(np.float32)])

def get_palette_list(colours_lab):
    # Convert LAB palette to flat RGB list for PIL
    rgb_palette = cv2.cvtColor(colours_lab[None,:,:], cv2.COLOR_LAB2RGB)
    rgb_palette = (np.clip(rgb_palette * 255, 0, 255)).astype(np.uint8)
    flat = rgb_palette.flatten().tolist()
    # Pad to 768 bytes
    return flat + [0, 0, 0] * (256 - len(colours_lab))
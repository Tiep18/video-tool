import time
from PIL import Image
import numpy as np

def benchmark():
    # Create a dummy image
    img = Image.new("RGB", (1080, 1920), (128, 128, 128))
    
    # Define crop box for scale = 1.08
    crop_w, crop_h = 1000, 1777
    x0, y0 = 40, 71
    
    # 1. BILINEAR
    start = time.time()
    for _ in range(500):
        cropped = img.crop((x0, y0, x0 + crop_w, y0 + crop_h))
        resized = cropped.resize((1080, 1920), Image.BILINEAR)
        arr = np.array(resized)
    end = time.time()
    print(f"BILINEAR: {end - start:.4f} seconds for 500 frames ({(end - start)/500*1000:.2f} ms/frame)")
    
    # 2. NEAREST
    start = time.time()
    for _ in range(500):
        cropped = img.crop((x0, y0, x0 + crop_w, y0 + crop_h))
        resized = cropped.resize((1080, 1920), Image.NEAREST)
        arr = np.array(resized)
    end = time.time()
    print(f"NEAREST: {end - start:.4f} seconds for 500 frames ({(end - start)/500*1000:.2f} ms/frame)")

    # 3. BOX
    start = time.time()
    for _ in range(500):
        cropped = img.crop((x0, y0, x0 + crop_w, y0 + crop_h))
        resized = cropped.resize((1080, 1920), Image.BOX)
        arr = np.array(resized)
    end = time.time()
    print(f"BOX: {end - start:.4f} seconds for 500 frames ({(end - start)/500*1000:.2f} ms/frame)")

    # 4. HAMMING
    start = time.time()
    for _ in range(500):
        cropped = img.crop((x0, y0, x0 + crop_w, y0 + crop_h))
        resized = cropped.resize((1080, 1920), Image.HAMMING)
        arr = np.array(resized)
    end = time.time()
    print(f"HAMMING: {end - start:.4f} seconds for 500 frames ({(end - start)/500*1000:.2f} ms/frame)")

if __name__ == "__main__":
    benchmark()

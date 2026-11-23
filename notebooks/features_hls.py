import cv2
import numpy as np
from PIL import Image

def extract_hls_features(image_path):

    # Abrimos la imagen igual que en RGB
    with Image.open(image_path) as img:
        rgb = np.array(img.convert("RGB"))

        # Convertimos RGB a HLS
        hls = cv2.cvtColor(rgb, cv2.COLOR_RGB2HLS)

        # Separamos los canales
        h = hls[:, :, 0]
        l = hls[:, :, 1]
        s = hls[:, :, 2]

        # Luminosidad y saturación: como hacíamos en RGB
        l_mean = l.mean() / 255
        l_std = l.std() / 255

        s_mean = s.mean() / 255
        s_std = s.std() / 255

        # El tono H es circular
        angulos = h.astype(float) * 2 * np.pi / 180

        h_sin_mean = np.sin(angulos).mean()
        h_cos_mean = np.cos(angulos).mean()

        h_concentration = np.sqrt(
            h_sin_mean ** 2 + h_cos_mean ** 2
        )

        return {
            "h_sin_mean": float(h_sin_mean),
            "h_cos_mean": float(h_cos_mean),
            "h_concentration": float(h_concentration),
            "l_mean": float(l.mean()),
            "l_std": float(l.std()),
            "s_mean": float(s.mean()),
            "s_std": float(s.std())
        }


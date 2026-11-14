"""
Script de calibración de umbrales para clasificación de morfología facial.
(necesitaba 4 ejemplos para percibir los ratios reales de cada tipo de rostro)

CÓMO USARLO:
1. Coloca este archivo en la misma carpeta que tu server.py
   (para que encuentre face_landmarker.task ya descargado, o lo descargue).
2. Pon las 4 fotos de referencia en una carpeta "referencias/" con estos nombres:
   - referencias/redondo.png
   - referencias/ovalado.jpg
   - referencias/diamante.jpg
   - referencias/cuadrado.jpeg
3. Corre: python calibrar_rostros.py
4. Verás los ratios reales de cada rostro para ajustar los umbrales en server.py
"""

import os
import math
import urllib.request
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "face_landmarker.task")
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"

if not os.path.exists(MODEL_PATH):
    print(f"Descargando modelo desde {MODEL_URL}...")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    print("Modelo descargado.")

base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
options = vision.FaceLandmarkerOptions(
    base_options=base_options,
    output_face_blendshapes=False,
    output_facial_transformation_matrixes=False,
    num_faces=1
)
detector = vision.FaceLandmarker.create_from_options(options)


def calcular_distancia(p1, p2, ancho, alto):
    x1, y1 = p1.x * ancho, p1.y * alto
    x2, y2 = p2.x * ancho, p2.y * alto
    return math.hypot(x2 - x1, y2 - y1)


def analizar_imagen(ruta):
    img = cv2.imread(ruta)
    if img is None:
        print(f"  ❌ No se pudo leer {ruta}")
        return None

    alto, ancho, _ = img.shape
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)
    resultado = detector.detect(mp_image)

    if not resultado.face_landmarks:
        print(f"  ❌ No se detectó rostro en {ruta}")
        return None

    p = resultado.face_landmarks[0]

    largo = calcular_distancia(p[10], p[152], ancho, alto)
    pomulos = calcular_distancia(p[234], p[454], ancho, alto)
    frente = calcular_distancia(p[54], p[284], ancho, alto)
    mandibula = calcular_distancia(p[172], p[397], ancho, alto)

    ratio_largo = largo / pomulos
    ratio_frente = frente / pomulos
    ratio_mandibula = mandibula / pomulos

    return {
        "ratio_largo": round(ratio_largo, 3),
        "ratio_frente": round(ratio_frente, 3),
        "ratio_mandibula": round(ratio_mandibula, 3),
    }


if __name__ == "__main__":
    referencias = {
        "REDONDO":  "referencias/redondo.png",
        "OVALADO":  "referencias/ovalado.jpg",
        "DIAMANTE": "referencias/diamante.jpg",
        "CUADRADO": "referencias/cuadrado.jpeg",
    }

    print("\n=== RESULTADOS DE CALIBRACIÓN ===\n")
    resultados = {}
    for nombre, ruta in referencias.items():
        print(f"{nombre} ({ruta}):")
        r = analizar_imagen(ruta)
        if r:
            print(f"  largo/pomulos    = {r['ratio_largo']}")
            print(f"  frente/pomulos   = {r['ratio_frente']}")
            print(f"  mandibula/pomulos= {r['ratio_mandibula']}")
            resultados[nombre] = r
        print()

    print("=== TABLA RESUMEN ===")
    print(f"{'Tipo':<10} {'largo':<8} {'frente':<8} {'mandibula':<10}")
    for nombre, r in resultados.items():
        print(f"{nombre:<10} {r['ratio_largo']:<8} {r['ratio_frente']:<8} {r['ratio_mandibula']:<10}")

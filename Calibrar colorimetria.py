"""
Script de calibración de parámetros para clasificación de colorimetría estacional
(Invierno / Verano / Otoño / Primavera).

Mide, a partir del rostro detectado:
  - Temperatura de piel (subtono cálido/frío) usando el canal b* de Lab
  - Matiz de piel (a* de Lab, componente rojo-verde)
  - Luminosidad de piel, cabello y ojos (L* de Lab)
  - Contraste piel-cabello y piel-ojos (diferencias de luminosidad)
  - Saturación/croma de la piel (qué tan "viva" o "apagada" es)

CORRECCIÓN DE BALANCE DE BLANCOS (nuevo):
Antes de calcular los parámetros de piel/cabello/ojos, el script muestrea la
esclerótica (el blanco del ojo) como punto de referencia neutro. En teoría,
la esclerótica debería verse gris/blanca sin importar el subtono de piel de
la persona — si en la foto sale con un tinte cálido o frío, es la LUZ la que
tiene ese tinte, no la piel. El script calcula esa desviación y la resta de
todas las mediciones de color, para que la temperatura de la luz ambiente no
se confunda con el subtono real de la persona.

CÓMO USARLO:
1. Coloca este archivo en la misma carpeta que tu server.py de colorimetría
   (para que encuentre face_landmarker.task ya descargado, o lo descargue).
2. Crea una carpeta "referencias_color/" y guarda ahí 4 fotos de referencia,
   una por estación, con estos nombres de archivo (cualquier extensión: jpg/jpeg/png/webp):
   - referencias_color/invierno.*
   - referencias_color/verano.*
   - referencias_color/otono.*
   - referencias_color/primavera.*
3. Usa fotos con buena luz natural, sin filtros ni maquillaje pesado, cabello
   visible (evita gorros/turbantes), ojos bien abiertos mirando al frente
   (para que la esclerótica sea visible) y fondo neutro si es posible.
4. Corre: python calibrar_colorimetria.py
5. Verás los valores reales (ya corregidos) de cada estación para ajustar
   los umbrales en tu server.py.

NOTA 1: el muestreo de "cabello" es una aproximación (no hay landmark de
cabello en MediaPipe): se toma una franja por encima de la línea de la
frente. En fotos con recogidos altos, cabello muy corto o flequillo, este
valor puede ser menos preciso — revísalo si un resultado se ve raro.

NOTA 2: si el script imprime una advertencia de "referencia blanca dudosa",
probablemente los ojos estaban cerrados, mirando de lado, o había mucho
brillo/sombra sobre ellos — considera repetir esa foto.
"""

import os
import glob
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

# Puntos de piel (mejilla izq, mejilla der, entrecejo) - zonas mate, sin sombras duras
PUNTOS_PIEL = [50, 280, 151]
# Iris (aprox. centro de ojo) - MediaPipe Tasks entrega 478 puntos, incluye iris
PUNTO_IRIS_IZQ = 468
PUNTO_IRIS_DER = 473
# Esquinas externas de cada ojo, usadas junto al iris para ubicar la esclerótica
PUNTO_ESQUINA_EXT_OJO_IZQ = 263
PUNTO_ESQUINA_EXT_OJO_DER = 33
# Referencias para ubicar la franja de "cabello" por extrapolación
PUNTO_FRENTE_ARRIBA = 10
PUNTO_MENTON = 152

# Valor objetivo neutro para la corrección (blanco/gris "puro" en Lab de cv2)
NEUTRO_AB = 128.0
L_OBJETIVO_ESCLEROTICA = 200.0  # luminosidad típica de una esclerótica bien iluminada


def punto_px(p, ancho, alto):
    return int(p.x * ancho), int(p.y * alto)


def muestra_patch(img_lab, cx, cy, radio, ancho, alto):
    """Devuelve el color Lab promedio de un parche cuadrado, recortado a los bordes."""
    x1, x2 = max(0, cx - radio), min(ancho, cx + radio)
    y1, y2 = max(0, cy - radio), min(alto, cy + radio)
    if x2 <= x1 or y2 <= y1:
        return None
    parche = img_lab[y1:y2, x1:x2].reshape(-1, 3)
    return {
        "L": float(np.mean(parche[:, 0])),
        "a": float(np.mean(parche[:, 1])),
        "b": float(np.mean(parche[:, 2])),
    }


def obtener_referencia_blanca(p, img_lab, ancho, alto, radio):
    """
    Muestrea la esclerótica (blanco del ojo) en un punto entre el centro del
    iris y la esquina externa del ojo, para ambos ojos, y promedia.
    """
    pares = [
        (PUNTO_IRIS_IZQ, PUNTO_ESQUINA_EXT_OJO_IZQ),
        (PUNTO_IRIS_DER, PUNTO_ESQUINA_EXT_OJO_DER),
    ]
    muestras = []
    for idx_iris, idx_esquina in pares:
        ix, iy = punto_px(p[idx_iris], ancho, alto)
        ex, ey = punto_px(p[idx_esquina], ancho, alto)
        # Punto intermedio entre iris y esquina externa -> cae sobre la esclerótica
        mx, my = int((ix + ex) / 2), int((iy + ey) / 2)
        m = muestra_patch(img_lab, mx, my, radio, ancho, alto)
        if m:
            muestras.append(m)
    if not muestras:
        return None
    return {
        "L": float(np.mean([m["L"] for m in muestras])),
        "a": float(np.mean([m["a"] for m in muestras])),
        "b": float(np.mean([m["b"] for m in muestras])),
    }


def analizar_imagen(ruta):
    img = cv2.imread(ruta)
    if img is None:
        print(f"  ❌ No se pudo leer {ruta}")
        return None

    alto, ancho, _ = img.shape
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    # cv2 Lab: L en [0,255] (≈L*/100*255), a y b centrados en 128 (≈ a*/b* + 128)
    img_lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)

    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)
    resultado = detector.detect(mp_image)

    if not resultado.face_landmarks:
        print(f"  ❌ No se detectó rostro en {ruta}")
        return None

    p = resultado.face_landmarks[0]
    radio_patch = max(4, int(0.02 * ancho))
    radio_esclerotica = max(2, int(0.008 * ancho))

    # --- Referencia blanca (esclerótica) ---
    ref = obtener_referencia_blanca(p, img_lab, ancho, alto, radio_esclerotica)
    advertencia_ref = None
    if ref is None:
        corr_a, corr_b, escala_L = 0.0, 0.0, 1.0
        advertencia_ref = "no se pudo muestrear la esclerótica; se usó sin corregir"
    else:
        corr_a = NEUTRO_AB - ref["a"]
        corr_b = NEUTRO_AB - ref["b"]
        escala_L = L_OBJETIVO_ESCLEROTICA / ref["L"] if ref["L"] > 5 else 1.0
        escala_L = min(max(escala_L, 0.5), 2.0)  # limitar corrección a un rango razonable
        if ref["L"] < 110 or ref["L"] > 250:
            advertencia_ref = f"referencia blanca dudosa (L*={ref['L']:.1f}); revisa esa foto"

    # --- Piel: promedio de 3 puntos ---
    muestras_piel = []
    for idx in PUNTOS_PIEL:
        cx, cy = punto_px(p[idx], ancho, alto)
        m = muestra_patch(img_lab, cx, cy, radio_patch, ancho, alto)
        if m:
            muestras_piel.append(m)
    if not muestras_piel:
        print(f"  ❌ No se pudo muestrear piel en {ruta}")
        return None
    piel_L = np.mean([m["L"] for m in muestras_piel]) * escala_L
    piel_a = np.mean([m["a"] for m in muestras_piel]) + corr_a
    piel_b = np.mean([m["b"] for m in muestras_piel]) + corr_b

    # --- Cabello: franja extrapolada por encima de la línea de frente ---
    fx, fy = punto_px(p[PUNTO_FRENTE_ARRIBA], ancho, alto)
    mx, my = punto_px(p[PUNTO_MENTON], ancho, alto)
    alto_rostro = math.hypot(mx - fx, my - fy)
    cabello_y = int(fy - 0.28 * alto_rostro)
    m_cabello = muestra_patch(img_lab, fx, cabello_y, radio_patch, ancho, alto)
    cabello_L = m_cabello["L"] * escala_L if m_cabello else None

    # --- Ojos: iris izq/der ---
    muestras_ojo = []
    for idx in [PUNTO_IRIS_IZQ, PUNTO_IRIS_DER]:
        cx, cy = punto_px(p[idx], ancho, alto)
        m = muestra_patch(img_lab, cx, cy, max(3, radio_patch // 2), ancho, alto)
        if m:
            muestras_ojo.append(m)
    ojo_L = np.mean([m["L"] for m in muestras_ojo]) * escala_L if muestras_ojo else None

    piel_L = min(max(piel_L, 0), 255)
    piel_a = min(max(piel_a, 0), 255)
    piel_b = min(max(piel_b, 0), 255)
    if cabello_L is not None:
        cabello_L = min(max(cabello_L, 0), 255)
    if ojo_L is not None:
        ojo_L = min(max(ojo_L, 0), 255)

    croma_piel = math.hypot(piel_a - 128, piel_b - 128)  # qué tan viva/saturada es la piel
    contraste_piel_cabello = abs(piel_L - cabello_L) if cabello_L is not None else None
    contraste_piel_ojos = abs(piel_L - ojo_L) if ojo_L is not None else None

    return {
        "piel_L": round(piel_L, 1),
        "piel_a": round(piel_a - 128, 1),   # negativo=verdoso, positivo=rojizo
        "piel_b": round(piel_b - 128, 1),   # negativo=azulado(frío), positivo=amarillento(cálido)
        "croma_piel": round(croma_piel, 1),
        "cabello_L": round(cabello_L, 1) if cabello_L is not None else None,
        "ojo_L": round(ojo_L, 1) if ojo_L is not None else None,
        "contraste_piel_cabello": round(contraste_piel_cabello, 1) if contraste_piel_cabello is not None else None,
        "contraste_piel_ojos": round(contraste_piel_ojos, 1) if contraste_piel_ojos is not None else None,
        "ref_blanca_L": round(ref["L"], 1) if ref else None,
        "advertencia": advertencia_ref,
    }


def encontrar_archivo(carpeta, nombre_base):
    """Busca referencias_color/<nombre_base>.<cualquier extensión común>"""
    for ext in ("jpg", "jpeg", "png", "webp"):
        candidatos = glob.glob(os.path.join(carpeta, f"{nombre_base}.{ext}"))
        if candidatos:
            return candidatos[0]
    return None


if __name__ == "__main__":
    carpeta = os.path.join(BASE_DIR, "referencias_color")
    estaciones = {
        "INVIERNO":  "invierno",
        "VERANO":    "verano",
        "OTOÑO":     "otono",
        "PRIMAVERA": "primavera",
    }

    print("\n=== RESULTADOS DE CALIBRACIÓN DE COLORIMETRÍA (corregido por balance de blancos) ===\n")
    resultados = {}
    for nombre, base in estaciones.items():
        ruta = encontrar_archivo(carpeta, base)
        if not ruta:
            print(f"{nombre}: ⚠️  no se encontró referencias_color/{base}.(jpg|jpeg|png|webp)\n")
            continue

        print(f"{nombre} ({os.path.basename(ruta)}):")
        r = analizar_imagen(ruta)
        if r:
            print(f"  piel L*             = {r['piel_L']}   (luminosidad de piel)")
            print(f"  piel a*             = {r['piel_a']}   (- verdoso / + rojizo)")
            print(f"  piel b*             = {r['piel_b']}   (- azulado/frío / + amarillento/cálido)")
            print(f"  croma piel          = {r['croma_piel']}   (saturación: alto=vivo, bajo=apagado)")
            print(f"  cabello L*          = {r['cabello_L']}")
            print(f"  ojo L*              = {r['ojo_L']}")
            print(f"  contraste piel-pelo = {r['contraste_piel_cabello']}")
            print(f"  contraste piel-ojos = {r['contraste_piel_ojos']}")
            print(f"  ref. esclerótica L* = {r['ref_blanca_L']}   (antes de corregir; ideal ~180-220)")
            if r["advertencia"]:
                print(f"  ⚠️  {r['advertencia']}")
            resultados[nombre] = r
        print()

    if resultados:
        print("=== TABLA RESUMEN ===")
        encabezados = ["Estación", "piel_L", "piel_a", "piel_b", "croma", "cab_L", "ojo_L", "cnt_pelo", "cnt_ojos"]
        print(f"{encabezados[0]:<11}{encabezados[1]:<8}{encabezados[2]:<8}{encabezados[3]:<8}{encabezados[4]:<8}{encabezados[5]:<8}{encabezados[6]:<8}{encabezados[7]:<10}{encabezados[8]:<10}")
        for nombre, r in resultados.items():
            print(f"{nombre:<11}{r['piel_L']:<8}{r['piel_a']:<8}{r['piel_b']:<8}{r['croma_piel']:<8}"
                  f"{str(r['cabello_L']):<8}{str(r['ojo_L']):<8}{str(r['contraste_piel_cabello']):<10}{str(r['contraste_piel_ojos']):<10}")
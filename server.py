# server.py
import os
import math
import json
import secrets
import shutil
import urllib.request
from datetime import datetime
from typing import Optional

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, Depends, Header, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session
import bcrypt
import mediapipe as mp

# --- Base de datos ---
from database import engine, Base, get_db, SessionLocal
from models import Usuario, Producto, HistorialAnalisis, Sesion, Interes  # noqa: F401

app = FastAPI(title="Motor de Inteligencia - Morfología, Colorimetría y Catálogo")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Crear tablas si no existen (incluye la nueva tabla `sesiones` e `intereses`)
try:
    Base.metadata.create_all(bind=engine)
    print("✅ Base de datos conectada y tablas listas.")
except Exception as e:
    print(f"❌ Error al conectar con la base de datos al iniciar: {e}")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "face_landmarker.task")
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
CATALOGO_DIR = os.path.join(BASE_DIR, "catalogo")
CONOCIMIENTO_DIR = os.path.join(BASE_DIR, "conocimiento")

if os.path.isdir(CATALOGO_DIR):
    app.mount("/catalogo", StaticFiles(directory=CATALOGO_DIR), name="catalogo")
if os.path.isdir(CONOCIMIENTO_DIR):
    app.mount("/conocimiento", StaticFiles(directory=CONOCIMIENTO_DIR), name="conocimiento")


# ============================================================
#  AUTENTICACIÓN REAL (paso 3)
#
#  Reemplaza el placeholder de admin del paso 2:
#  - Las contraseñas se hashean con bcrypt nativo antes de guardarse.
#  - Al hacer login se crea una fila en la tabla `sesiones` con un token
#    aleatorio y una fecha de expiración (30 días). El token se devuelve
#    al frontend, que lo manda en el header X-Auth-Token en cada request.
#  - No hay una "contraseña de admin" global; el admin es simplemente un
#    Usuario con es_admin=True (creado con el script crear_admin.py).
# ============================================================

def _hashear_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def _verificar_password(password: str, password_hash: str) -> bool:
    try:
        pwd_bytes = password.encode("utf-8")[:72]
        hash_bytes = password_hash.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        return False


def _crear_sesion(db: Session, usuario: Usuario) -> Sesion:
    sesion = Sesion(
        token=secrets.token_urlsafe(48),
        usuario_id=usuario.id,
    )
    db.add(sesion)
    db.commit()
    db.refresh(sesion)
    return sesion


def _obtener_usuario_del_token(db: Session, token: Optional[str]) -> Optional[Usuario]:
    """Devuelve el Usuario dueño del token, o None si es inválido/expirado."""
    if not token:
        return None
    sesion = db.query(Sesion).filter(Sesion.token == token).first()
    if not sesion or not sesion.esta_vigente():
        return None
    return sesion.usuario


def usuario_actual(
    x_auth_token: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Usuario:
    """Dependencia: exige un usuario logueado válido, o 401."""
    u = _obtener_usuario_del_token(db, x_auth_token)
    if not u:
        raise HTTPException(status_code=401, detail="No autenticado")
    return u


def usuario_opcional(
    x_auth_token: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Optional[Usuario]:
    """Dependencia: si hay token válido devuelve el Usuario; si no, None (no falla)."""
    return _obtener_usuario_del_token(db, x_auth_token)


def admin_requerido(u: Usuario = Depends(usuario_actual)) -> Usuario:
    """Dependencia: exige usuario logueado con es_admin=True."""
    if not u.es_admin:
        raise HTTPException(status_code=403, detail="Se requieren permisos de administrador")
    return u


# ============================================================
#  ENDPOINTS DE AUTH
# ============================================================

@app.post("/api/auth/registrar")
def auth_registrar(datos: dict = Body(...), db: Session = Depends(get_db)):
    """Crea una cuenta nueva y devuelve un token de sesión (login automático)."""
    nombre = (datos.get("nombre") or "").strip()
    correo = (datos.get("correo") or "").strip().lower()
    password = datos.get("password") or ""

    if not nombre or not correo or not password:
        raise HTTPException(status_code=400, detail="Nombre, correo y contraseña son obligatorios")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")
    if "@" not in correo or "." not in correo:
        raise HTTPException(status_code=400, detail="Correo con formato inválido")

    if db.query(Usuario).filter(Usuario.correo == correo).first():
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese correo")

    nuevo = Usuario(
        nombre=nombre,
        correo=correo,
        password_hash=_hashear_password(password),
        es_admin=False,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)

    sesion = _crear_sesion(db, nuevo)
    return {"token": sesion.token, "usuario": nuevo.como_dict()}


@app.post("/api/auth/login")
def auth_login(datos: dict = Body(...), db: Session = Depends(get_db)):
    correo = (datos.get("correo") or "").strip().lower()
    password = datos.get("password") or ""

    if not correo or not password:
        raise HTTPException(status_code=400, detail="Falta correo o contraseña")

    usuario = db.query(Usuario).filter(Usuario.correo == correo).first()
    if not usuario or not _verificar_password(password, usuario.password_hash):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")

    sesion = _crear_sesion(db, usuario)
    return {"token": sesion.token, "usuario": usuario.como_dict()}


@app.post("/api/auth/logout")
def auth_logout(
    x_auth_token: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Cierra la sesión actual borrando la fila de `sesiones`."""
    if x_auth_token:
        db.query(Sesion).filter(Sesion.token == x_auth_token).delete()
        db.commit()
    return {"estatus": "ok"}


@app.get("/api/auth/actual")
def auth_actual(
    x_auth_token: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Devuelve datos del usuario logueado, o null si no hay sesión válida.
    NO tira 401 — lo usa el header dinámico para saber qué botones mostrar.
    """
    u = _obtener_usuario_del_token(db, x_auth_token)
    if not u:
        return {"usuario": None}
    return {"usuario": u.como_dict()}


# ============================================================
#  Detector MediaPipe (sin cambios)
# ============================================================

landmarker_detector = None
legacy_face_mesh = None

def init_detector():
    global landmarker_detector, legacy_face_mesh
    try:
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
        if not os.path.exists(MODEL_PATH):
            print(f"Descargando modelo face_landmarker.task desde {MODEL_URL}...")
            urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
            print("Modelo descargado exitosamente.")
        base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
            num_faces=1,
        )
        landmarker_detector = vision.FaceLandmarker.create_from_options(options)
        print("MediaPipe FaceLandmarker inicializado correctamente.")
    except Exception as e:
        print(f"No se pudo inicializar MediaPipe Tasks ({e}), intentando mp.solutions...")
        try:
            if hasattr(mp, "solutions") and hasattr(mp.solutions, "face_mesh"):
                legacy_face_mesh = mp.solutions.face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1)
                print("MediaPipe solutions FaceMesh inicializado.")
        except Exception as e2:
            print(f"Error al inicializar FaceMesh legacy: {e2}")

init_detector()


def calcular_distancia(p1, p2, ancho, alto):
    x1, y1 = p1.x * ancho, p1.y * alto
    x2, y2 = p2.x * ancho, p2.y * alto
    return math.hypot(x2 - x1, y2 - y1)


# ============================================================
#  MORFOLOGÍA
# ============================================================

MAPA_MORFOLOGIA = {"Redondo": "MRE", "Cuadrado": "MCU", "Diamante": "MDI", "Ovalado": "MOV"}
ASESORIA_MORFOLOGIA = {
    "Redondo": "Busca monturas angulares o rectangulares: aportan estructura y contrastan con la suavidad de tus rasgos.",
    "Cuadrado": "Prueba monturas redondeadas u ovaladas: suavizan los ángulos marcados de tu mandíbula.",
    "Diamante": "Las monturas ovaladas o cat-eye suave equilibran bien unos pómulos prominentes.",
    "Ovalado": "Tu rostro es versátil: casi cualquier forma de montura te va a quedar bien.",
}

def clasificar(landmarks, ancho, alto):
    p = landmarks
    largo = calcular_distancia(p[10], p[152], ancho, alto)
    pomulos = calcular_distancia(p[234], p[454], ancho, alto)
    mandibula = calcular_distancia(p[172], p[397], ancho, alto)
    ratio_largo = largo / pomulos
    ratio_mandibula = mandibula / pomulos

    if ratio_mandibula < 0.77:
        return "Diamante"
    elif ratio_mandibula >= 0.79:
        if ratio_largo >= 1.19:
            return "Cuadrado"
        else:
            return "Redondo"
    else:
        return "Ovalado"


# ============================================================
#  COLORIMETRÍA
# ============================================================

PUNTOS_PIEL_COLOR = [50, 280, 151]
PUNTO_IRIS_IZQ = 468
PUNTO_IRIS_DER = 473
PUNTO_FRENTE_ARRIBA_COLOR = 10
PUNTO_MENTON_COLOR = 152

UMBRAL_TEMPERATURA = 15.0
UMBRAL_CABELLO_OSCURO = 60.0
UMBRAL_CABELLO_CLARO = 104.0

MAPA_ESTACION = {"Invierno": "CIN", "Verano": "CVE", "Otoño": "COT", "Primavera": "CPR"}
ASESORIA_ESTACION = {
    "Invierno": "Te favorecen los colores fríos e intensos: negro, plateado, azul marino.",
    "Verano": "Busca tonos suaves y fríos: gris perla, rosa palo, azul cielo.",
    "Otoño": "Los tonos cálidos y terrosos son los tuyos: carey, bronce, verde oliva, mostaza.",
    "Primavera": "Colores cálidos y luminosos te sientan mejor: dorado, coral, melocotón, turquesa.",
    "Indeterminado": "No pudimos determinar tu estación de color con esta foto; intenta con mejor luz natural.",
}

def punto_px(p, ancho, alto):
    return int(p.x * ancho), int(p.y * alto)

def muestra_patch(img_lab, cx, cy, radio, ancho, alto):
    x1, x2 = max(0, cx - radio), min(ancho, cx + radio)
    y1, y2 = max(0, cy - radio), min(alto, cy + radio)
    if x2 <= x1 or y2 <= y1:
        return None
    parche = img_lab[y1:y2, x1:x2].reshape(-1, 3)
    return {"L": float(np.mean(parche[:, 0])), "a": float(np.mean(parche[:, 1])), "b": float(np.mean(parche[:, 2]))}

def extraer_parametros_color(landmarks, img_lab, ancho, alto):
    p = landmarks
    if len(p) <= PUNTO_IRIS_DER:
        return None
    radio_patch = max(4, int(0.02 * ancho))
    muestras_piel = []
    for idx in PUNTOS_PIEL_COLOR:
        cx, cy = punto_px(p[idx], ancho, alto)
        m = muestra_patch(img_lab, cx, cy, radio_patch, ancho, alto)
        if m:
            muestras_piel.append(m)
    if not muestras_piel:
        return None
    piel_b = np.mean([m["b"] for m in muestras_piel]) - 128
    fx, fy = punto_px(p[PUNTO_FRENTE_ARRIBA_COLOR], ancho, alto)
    mx, my = punto_px(p[PUNTO_MENTON_COLOR], ancho, alto)
    alto_rostro = math.hypot(mx - fx, my - fy)
    cabello_y = int(fy - 0.28 * alto_rostro)
    m_cabello = muestra_patch(img_lab, fx, cabello_y, radio_patch, ancho, alto)
    cabello_L = m_cabello["L"] if m_cabello else None
    return {"piel_b": piel_b, "cabello_L": cabello_L}

def clasificar_estacion(landmarks, img_lab, ancho, alto):
    parametros = extraer_parametros_color(landmarks, img_lab, ancho, alto)
    if parametros is None or parametros["cabello_L"] is None:
        return "Indeterminado"
    if parametros["piel_b"] < UMBRAL_TEMPERATURA:
        return "Invierno"
    cabello_L = parametros["cabello_L"]
    if cabello_L < UMBRAL_CABELLO_OSCURO:
        return "Verano"
    elif cabello_L < UMBRAL_CABELLO_CLARO:
        return "Otoño"
    else:
        return "Primavera"


# ============================================================
#  CATÁLOGO — desde BD
# ============================================================

CATEGORIAS_DISPONIBLES = ["lentes", "bufandas", "cintillo", "chaqueta", "franelas"]
CODIGOS_COLORIMETRIA = {"CIN", "CVE", "COT", "CPR"}
CODIGOS_MORFOLOGIA = {"MRE", "MCU", "MDI", "MOV"}
CODIGOS_VALIDOS = CODIGOS_COLORIMETRIA | CODIGOS_MORFOLOGIA


def _serializar_producto_publico(p: Producto) -> dict:
    return {
        "sku": p.sku,
        "descripcion": p.nombre,
        "imagen_url": p.imagen_url,
        "precio": p.precio,
    }


def obtener_modelos_desde_bd(db: Session, codigo: str, categorias=None) -> dict:
    if not codigo:
        return {}
    categorias = categorias or CATEGORIAS_DISPONIBLES
    productos = (
        db.query(Producto)
        .filter(
            Producto.codigo_resultado == codigo,
            Producto.activo.is_(True),
            Producto.categoria.in_(categorias),
        )
        .order_by(Producto.categoria, Producto.sku)
        .all()
    )
    agrupado = {}
    for p in productos:
        agrupado.setdefault(p.categoria, []).append(_serializar_producto_publico(p))
    return {cat: agrupado[cat] for cat in categorias if cat in agrupado}


# ============================================================
#  ENDPOINT DE ANÁLISIS
#
#  Cambio del paso 3: si viene el header X-Auth-Token con una sesión válida,
#  guarda el análisis en HistorialAnalisis para ese usuario. Si no hay token
#  o es inválido, el análisis funciona igual pero no se guarda (opt-in).
# ============================================================

@app.post("/api/analizar")
async def analizar_rostro(
    imagen: UploadFile = File(...),
    categoria: str = Form(""),
    db: Session = Depends(get_db),
    quien: Optional[Usuario] = Depends(usuario_opcional),
):
    try:
        bytes_img = await imagen.read()
        nparr = np.frombuffer(bytes_img, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return JSONResponse(status_code=400, content={"error": "Imagen no válida."})

        alto, ancho, _ = img.shape
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        landmarks = None
        if landmarker_detector is not None:
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)
            resultados = landmarker_detector.detect(mp_image)
            if resultados.face_landmarks and len(resultados.face_landmarks) > 0:
                landmarks = resultados.face_landmarks[0]
        elif legacy_face_mesh is not None:
            resultados = legacy_face_mesh.process(img_rgb)
            if resultados.multi_face_landmarks:
                landmarks = resultados.multi_face_landmarks[0].landmark

        if landmarks is None:
            return JSONResponse(status_code=404, content={"error": "No se detectó rostro en la imagen."})

        categorias_pedidas = None
        if categoria and categoria.strip().lower() != "todas":
            categorias_pedidas = [categoria.strip().lower()]

        resultado_morfologia = clasificar(landmarks, ancho, alto)
        codigo_morfologia = MAPA_MORFOLOGIA.get(resultado_morfologia)
        modelos_morfologia = obtener_modelos_desde_bd(db, codigo_morfologia, categorias_pedidas)

        img_lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        resultado_estacion = clasificar_estacion(landmarks, img_lab, ancho, alto)
        codigo_estacion = MAPA_ESTACION.get(resultado_estacion)
        modelos_colorimetria = obtener_modelos_desde_bd(db, codigo_estacion, categorias_pedidas)

        # Historial opt-in: solo si el usuario está logueado
        if quien is not None:
            skus_mostrados = []
            for grupo in (modelos_morfologia, modelos_colorimetria):
                for lista in grupo.values():
                    for m in lista:
                        skus_mostrados.append(m["sku"])
            registro = HistorialAnalisis(
                usuario_id=quien.id,
                morfologia_resultado=resultado_morfologia,
                estacion_resultado=resultado_estacion,
                skus_recomendados=json.dumps(sorted(set(skus_mostrados))),
            )
            db.add(registro)
            db.commit()

        return {
            "estatus": "ok",
            "categoria": categoria or "todas",
            "morfologia": resultado_morfologia,
            "asesoria_morfologia": ASESORIA_MORFOLOGIA.get(resultado_morfologia, ""),
            "modelos_morfologia": modelos_morfologia,
            "estacion": resultado_estacion,
            "asesoria_estacion": ASESORIA_ESTACION.get(resultado_estacion, ""),
            "modelos_colorimetria": modelos_colorimetria,
            "historial_guardado": quien is not None,
        }

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ============================================================
#  "ME INTERESA" (paso 4)
#
#  No es un carrito con checkout — es una señal de interés que se guarda
#  por clic. Requiere login (usuario_actual, no usuario_opcional): si no
#  hay sesión, el frontend debe mandar al usuario a login.html antes de
#  intentar guardar, porque sin usuario_id no hay a quién asociarlo.
# ============================================================

TIPOS_RECOMENDACION_VALIDOS = {"morfologia", "colorimetria"}


@app.post("/api/interes")
def guardar_interes(
    datos: dict = Body(...),
    db: Session = Depends(get_db),
    quien: Usuario = Depends(usuario_actual),
):
    sku = (datos.get("sku") or "").strip().upper()
    tipo_recomendacion = (datos.get("tipo_recomendacion") or "").strip().lower()

    if not sku:
        raise HTTPException(status_code=400, detail="Falta el SKU")
    if tipo_recomendacion not in TIPOS_RECOMENDACION_VALIDOS:
        raise HTTPException(
            status_code=400,
            detail=f"tipo_recomendacion debe ser uno de: {sorted(TIPOS_RECOMENDACION_VALIDOS)}",
        )
    if not db.query(Producto).filter(Producto.sku == sku).first():
        raise HTTPException(status_code=404, detail=f"No existe producto con SKU '{sku}'")

    nuevo = Interes(usuario_id=quien.id, sku=sku, tipo_recomendacion=tipo_recomendacion)
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo.como_dict()


@app.get("/api/mis-intereses")
def listar_mis_intereses(
    db: Session = Depends(get_db),
    quien: Usuario = Depends(usuario_actual),
):
    """Historial de 'Me interesa' del usuario logueado, con los datos del producto."""
    filas = (
        db.query(Interes)
        .filter(Interes.usuario_id == quien.id)
        .order_by(Interes.fecha.desc())
        .all()
    )
    resultado = []
    for i in filas:
        producto = db.query(Producto).filter(Producto.sku == i.sku).first()
        item = i.como_dict()
        item["producto"] = producto.como_dict() if producto else None
        resultado.append(item)
    return resultado


@app.delete("/api/interes/{interes_id}")
def eliminar_interes(
    interes_id: int,
    db: Session = Depends(get_db),
    quien: Usuario = Depends(usuario_actual),
):
    """Elimina un producto guardado en favoritos/intereses del usuario logueado."""
    item = (
        db.query(Interes)
        .filter(Interes.id == interes_id, Interes.usuario_id == quien.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Elemento no encontrado en tus favoritos")
    db.delete(item)
    db.commit()
    return {"estatus": "ok", "id": interes_id}


# ============================================================
#  PERFIL DE USUARIO Y DIAGNÓSTICO PERMANENTE
# ============================================================

@app.get("/api/usuario/perfil")
def api_usuario_perfil(
    db: Session = Depends(get_db),
    quien: Usuario = Depends(usuario_actual),
):
    """
    Devuelve los datos del perfil del usuario, su diagnóstico facial permanente más reciente,
    sus recomendaciones asociadas, su conteo de favoritos y el historial de análisis previos.
    """
    total_intereses = db.query(Interes).filter(Interes.usuario_id == quien.id).count()

    historial_filas = (
        db.query(HistorialAnalisis)
        .filter(HistorialAnalisis.usuario_id == quien.id)
        .order_by(HistorialAnalisis.fecha.desc())
        .all()
    )

    ultimo = historial_filas[0] if historial_filas else None
    ultimo_dict = None
    if ultimo:
        codigo_morf = MAPA_MORFOLOGIA.get(ultimo.morfologia_resultado)
        codigo_est = MAPA_ESTACION.get(ultimo.estacion_resultado)
        modelos_morf = obtener_modelos_desde_bd(db, codigo_morf)
        modelos_color = obtener_modelos_desde_bd(db, codigo_est)

        ultimo_dict = {
            "id": ultimo.id,
            "morfologia": ultimo.morfologia_resultado,
            "codigo_morfologia": codigo_morf,
            "asesoria_morfologia": ASESORIA_MORFOLOGIA.get(ultimo.morfologia_resultado, ""),
            "estacion": ultimo.estacion_resultado,
            "codigo_estacion": codigo_est,
            "asesoria_estacion": ASESORIA_ESTACION.get(ultimo.estacion_resultado, ""),
            "fecha": ultimo.fecha.isoformat(),
            "modelos_morfologia": modelos_morf,
            "modelos_colorimetria": modelos_color,
        }

    historial_resumen = []
    for h in historial_filas:
        historial_resumen.append({
            "id": h.id,
            "morfologia": h.morfologia_resultado,
            "estacion": h.estacion_resultado,
            "fecha": h.fecha.isoformat(),
        })

    return {
        "usuario": {
            "id": quien.id,
            "nombre": quien.nombre,
            "correo": quien.correo,
            "es_admin": quien.es_admin,
            "creado_en": quien.creado_en.isoformat() if quien.creado_en else None,
        },
        "diagnostico_permanente": ultimo_dict,
        "total_intereses": total_intereses,
        "historial_analisis": historial_resumen,
    }


# ============================================================
#  CATÁLOGO PÚBLICO (para catalogo-completo.html)
# ============================================================

@app.get("/api/catalogo")
def api_catalogo(
    db: Session = Depends(get_db),
    incluir_inactivos: bool = False,
    quien: Optional[Usuario] = Depends(usuario_opcional),
):
    # FIX seguridad: solo un admin logueado puede pedir los inactivos.
    # Si alguien sin permisos manda ?incluir_inactivos=true, se ignora en silencio.
    if incluir_inactivos and not (quien and quien.es_admin):
        incluir_inactivos = False

    query = db.query(Producto)
    if not incluir_inactivos:
        query = query.filter(Producto.activo.is_(True))
    resultado = {}
    for p in query.all():
        resultado[p.sku] = {
            "categoria": p.categoria,
            "codigo": p.codigo_resultado,
            "enfoque": p.enfoque,
            "descripcion": p.nombre,
            "precio": p.precio,
        }
    return resultado


# ============================================================
#  ADMIN: CRUD DE PRODUCTOS (requiere admin_requerido)
# ============================================================

def _validar_sku(sku: str) -> tuple:
    partes = sku.strip().upper().split("-")
    if len(partes) != 3 or not partes[0] or not partes[2]:
        raise HTTPException(status_code=400, detail=f"SKU inválido: '{sku}'. Formato esperado: PREFIJO-CODIGO-NUM (ej. LEN-CIN-01)")
    prefijo, codigo, _num = partes
    if codigo not in CODIGOS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"Código '{codigo}' no válido. Debe ser uno de: {sorted(CODIGOS_VALIDOS)}")
    return codigo, prefijo


def _deducir_enfoque(codigo: str) -> Optional[str]:
    if codigo in CODIGOS_COLORIMETRIA:
        return "colorimetria"
    if codigo in CODIGOS_MORFOLOGIA:
        return "morfologia"
    return None


@app.get("/api/admin/productos")
def admin_listar_productos(
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(admin_requerido),
):
    productos = db.query(Producto).order_by(Producto.categoria, Producto.codigo_resultado, Producto.sku).all()
    return [p.como_dict() for p in productos]


@app.post("/api/admin/productos")
async def admin_crear_producto(
    sku: str = Form(...),
    nombre: str = Form(...),
    categoria: str = Form(...),
    codigo_resultado: str = Form(...),
    precio: Optional[float] = Form(None),
    stock: int = Form(0),
    imagen: UploadFile = File(...),
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(admin_requerido),
):
    sku = sku.strip().upper()
    codigo_del_sku, _prefijo = _validar_sku(sku)

    categoria = categoria.strip().lower()
    if categoria not in CATEGORIAS_DISPONIBLES:
        raise HTTPException(status_code=400, detail=f"Categoría '{categoria}' no válida. Debe ser: {CATEGORIAS_DISPONIBLES}")

    codigo_resultado = codigo_resultado.strip().upper()
    if codigo_resultado not in CODIGOS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"Código '{codigo_resultado}' no válido")

    if codigo_resultado != codigo_del_sku:
        raise HTTPException(status_code=400, detail=f"Contradicción: el SKU trae '{codigo_del_sku}' pero elegiste código '{codigo_resultado}'")

    if db.query(Producto).filter(Producto.sku == sku).first():
        raise HTTPException(status_code=409, detail=f"Ya existe un producto con SKU '{sku}'")

    if not imagen.filename.lower().endswith(".png"):
        raise HTTPException(status_code=400, detail="La imagen debe ser un archivo .png")

    carpeta_destino = os.path.join(CATALOGO_DIR, categoria, codigo_resultado)
    os.makedirs(carpeta_destino, exist_ok=True)
    ruta_destino = os.path.join(carpeta_destino, f"{sku}.png")
    with open(ruta_destino, "wb") as f:
        shutil.copyfileobj(imagen.file, f)

    imagen_url = f"/catalogo/{categoria}/{codigo_resultado}/{sku}.png"
    nuevo = Producto(
        sku=sku, nombre=nombre.strip(),
        categoria=categoria, codigo_resultado=codigo_resultado,
        enfoque=_deducir_enfoque(codigo_resultado),
        precio=precio, stock=stock,
        imagen_url=imagen_url, activo=True,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo.como_dict()


@app.put("/api/admin/productos/{sku}")
def admin_editar_producto(
    sku: str,
    cambios: dict = Body(...),
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(admin_requerido),
):
    producto = db.query(Producto).filter(Producto.sku == sku.upper()).first()
    if not producto:
        raise HTTPException(status_code=404, detail=f"No existe producto con SKU '{sku}'")
    if "nombre" in cambios and cambios["nombre"] is not None:
        producto.nombre = str(cambios["nombre"]).strip()
    if "precio" in cambios:
        producto.precio = float(cambios["precio"]) if cambios["precio"] is not None else None
    if "stock" in cambios and cambios["stock"] is not None:
        producto.stock = int(cambios["stock"])
    if "activo" in cambios and cambios["activo"] is not None:
        producto.activo = bool(cambios["activo"])
    db.commit()
    db.refresh(producto)
    return producto.como_dict()


@app.post("/api/admin/productos/{sku}/imagen")
async def admin_reemplazar_imagen(
    sku: str,
    imagen: UploadFile = File(...),
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(admin_requerido),
):
    producto = db.query(Producto).filter(Producto.sku == sku.upper()).first()
    if not producto:
        raise HTTPException(status_code=404, detail=f"No existe producto con SKU '{sku}'")
    if not imagen.filename.lower().endswith(".png"):
        raise HTTPException(status_code=400, detail="La imagen debe ser un archivo .png")
    carpeta_destino = os.path.join(CATALOGO_DIR, producto.categoria, producto.codigo_resultado)
    os.makedirs(carpeta_destino, exist_ok=True)
    ruta_destino = os.path.join(carpeta_destino, f"{producto.sku}.png")
    with open(ruta_destino, "wb") as f:
        shutil.copyfileobj(imagen.file, f)
    db.commit()
    return producto.como_dict()


@app.delete("/api/admin/productos/{sku}")
def admin_eliminar_producto(
    sku: str,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(admin_requerido),
):
    producto = db.query(Producto).filter(Producto.sku == sku.upper()).first()
    if not producto:
        raise HTTPException(status_code=404, detail=f"No existe producto con SKU '{sku}'")
    producto.activo = False
    db.commit()
    return {"estatus": "ok", "sku": producto.sku, "activo": False}


# ============================================================
#  DIAGNÓSTICO Y ESTADÍSTICAS DEL NEGOCIO
# ============================================================

@app.get("/api/admin/estadisticas")
def admin_estadisticas(
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(admin_requerido),
):
    """
    Dashboard de Inteligencia Comercial y Demanda:
    - KPIs clave (usuarios, productos, análisis, intenciones de compra).
    - Ranking Top 10 de productos más deseados.
    - Distribución biométrica de clientes (morfologías y estaciones más comunes).
    - Desglose de demanda por categoría de prenda.
    - Actividad reciente.
    """
    total_usuarios = db.query(Usuario).count()
    total_admins = db.query(Usuario).filter(Usuario.es_admin.is_(True)).count()
    total_productos = db.query(Producto).count()
    total_activos = db.query(Producto).filter(Producto.activo.is_(True)).count()
    total_analisis = db.query(HistorialAnalisis).count()
    total_intereses = db.query(Interes).count()

    # 1. Top productos más deseados (con clics en "Me interesa")
    top_intereses_raw = (
        db.query(Interes.sku, func.count(Interes.id).label("total"))
        .group_by(Interes.sku)
        .order_by(func.count(Interes.id).desc())
        .limit(10)
        .all()
    )
    top_productos = []
    for sku, total_clics in top_intereses_raw:
        prod = db.query(Producto).filter(Producto.sku == sku).first()
        top_productos.append({
            "sku": sku,
            "total_deseos": total_clics,
            "nombre": prod.nombre if prod else sku,
            "categoria": prod.categoria if prod else "—",
            "precio": prod.precio if prod else None,
            "imagen_url": prod.imagen_url if prod else "",
            "codigo": prod.codigo_resultado if prod else "—",
        })

    # 2. Distribución de morfología
    dist_morfologia_raw = (
        db.query(HistorialAnalisis.morfologia_resultado, func.count(HistorialAnalisis.id))
        .filter(HistorialAnalisis.morfologia_resultado.isnot(None))
        .group_by(HistorialAnalisis.morfologia_resultado)
        .all()
    )
    dist_morfologia = {morf: count for morf, count in dist_morfologia_raw}

    # 3. Distribución de estación (colorimetría)
    dist_estacion_raw = (
        db.query(HistorialAnalisis.estacion_resultado, func.count(HistorialAnalisis.id))
        .filter(HistorialAnalisis.estacion_resultado.isnot(None))
        .group_by(HistorialAnalisis.estacion_resultado)
        .all()
    )
    dist_estacion = {est: count for est, count in dist_estacion_raw}

    # 4. Desglose de intereses por categoría de producto
    intereses_por_cat = {}
    for cat in CATEGORIAS_DISPONIBLES:
        c = (
            db.query(Interes)
            .join(Producto, Interes.sku == Producto.sku)
            .filter(Producto.categoria == cat)
            .count()
        )
        intereses_por_cat[cat] = c

    # 5. Actividad reciente de análisis
    ultimos_analisis = (
        db.query(HistorialAnalisis)
        .order_by(HistorialAnalisis.fecha.desc())
        .limit(6)
        .all()
    )
    recientes_analisis = []
    for a in ultimos_analisis:
        u = a.usuario
        recientes_analisis.append({
            "id": a.id,
            "usuario": u.nombre if u else "Anónimo",
            "correo": u.correo if u else "—",
            "morfologia": a.morfologia_resultado,
            "estacion": a.estacion_resultado,
            "fecha": a.fecha.isoformat(),
        })

    return {
        "kpis": {
            "total_usuarios": total_usuarios,
            "total_admins": total_admins,
            "total_productos": total_productos,
            "total_activos": total_activos,
            "total_analisis": total_analisis,
            "total_intereses": total_intereses,
        },
        "top_productos": top_productos,
        "distribucion_morfologia": dist_morfologia,
        "distribucion_colorimetria": dist_estacion,
        "intereses_por_categoria": intereses_por_cat,
        "actividad_reciente": recientes_analisis,
    }


@app.get("/api/db/status")
def db_status(
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(admin_requerido),
):
    total_usuarios = db.query(Usuario).count()
    total_admins = db.query(Usuario).filter(Usuario.es_admin.is_(True)).count()
    total_productos = db.query(Producto).count()
    total_activos = db.query(Producto).filter(Producto.activo.is_(True)).count()
    total_historial = db.query(HistorialAnalisis).count()
    total_sesiones = db.query(Sesion).count()

    productos_por_categoria = {}
    for cat in CATEGORIAS_DISPONIBLES:
        productos_por_categoria[cat] = (
            db.query(Producto).filter(Producto.categoria == cat, Producto.activo.is_(True)).count()
        )

    return {
        "estatus": "ok",
        "bd_activa": True,
        "tablas": {
            "usuarios": total_usuarios,
            "admins": total_admins,
            "productos": total_productos,
            "productos_activos": total_activos,
            "historial_analisis": total_historial,
            "sesiones_activas": total_sesiones,
        },
        "productos_por_categoria": productos_por_categoria,
    }


# ============================================================
#  RUTAS ESTÁTICAS
# ============================================================

def _servir_html(nombre_archivo: str):
    ruta = os.path.join(BASE_DIR, nombre_archivo)
    if not os.path.exists(ruta):
        return JSONResponse(status_code=404, content={"error": f"{nombre_archivo} no encontrado"})
    return FileResponse(ruta, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

def _servir_asset(nombre_archivo: str):
    ruta = os.path.join(BASE_DIR, nombre_archivo)
    if not os.path.exists(ruta):
        return JSONResponse(status_code=404, content={"error": f"{nombre_archivo} no encontrado"})
    return FileResponse(ruta, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

@app.get("/")
@app.get("/index.htm")
@app.get("/index.html")
async def servir_index():
    ruta = os.path.join(BASE_DIR, "index.htm")
    if not os.path.exists(ruta):
        ruta = os.path.join(BASE_DIR, "index.html")
    return FileResponse(ruta, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

@app.get("/styles.css")
async def servir_css(): return _servir_asset("styles.css")

@app.get("/script.js")
async def servir_js(): return _servir_asset("script.js")

@app.get("/auth.js")
async def servir_auth_js(): return _servir_asset("auth.js")

@app.get("/catalogo-completo.html")
async def servir_catalogo_html(): return _servir_html("catalogo-completo.html")

@app.get("/catalogo-completo.js")
async def servir_catalogo_js(): return _servir_asset("catalogo-completo.js")

@app.get("/conocimiento.html")
async def servir_conocimiento_html(): return _servir_html("conocimiento.html")

@app.get("/admin.html")
async def servir_admin_html(): return _servir_html("admin.html")

@app.get("/admin.js")
async def servir_admin_js(): return _servir_asset("admin.js")

@app.get("/login.html")
async def servir_login_html(): return _servir_html("login.html")

@app.get("/login.js")
async def servir_login_js(): return _servir_asset("login.js")

@app.get("/registro.html")
async def servir_registro_html(): return _servir_html("registro.html")

@app.get("/registro.js")
async def servir_registro_js(): return _servir_asset("registro.js")

@app.get("/favoritos.html")
@app.get("/favoritos")
async def servir_favoritos_html(): return _servir_html("favoritos.html")

@app.get("/favoritos.js")
async def servir_favoritos_js(): return _servir_asset("favoritos.js")

@app.get("/perfil.html")
@app.get("/perfil")
async def servir_perfil_html(): return _servir_html("perfil.html")

@app.get("/perfil.js")
async def servir_perfil_js(): return _servir_asset("perfil.js")

@app.get("/logo.png")
async def servir_logo():
    ruta_png = os.path.join(BASE_DIR, "logo.png")
    if os.path.exists(ruta_png):
        return FileResponse(ruta_png)
    ruta_jpg = os.path.join(BASE_DIR, "logo.jpg")
    if os.path.exists(ruta_jpg):
        return FileResponse(ruta_jpg)
    return JSONResponse(status_code=404, content={"error": "Logo no encontrado"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)

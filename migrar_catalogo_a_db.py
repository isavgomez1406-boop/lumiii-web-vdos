"""
Migración inicial del catálogo: lee catalogo/catalogo.json y llena la tabla
Productos de la base de datos.

CUÁNDO CORRERLO:
- La primera vez, después de arrancar el servidor una vez (para que las
  tablas ya existan en lumiii.db).
- Cada vez que agregues productos NUEVOS al Excel + regeneres catalogo.json,
  si todavía no estás usando el panel del vendedor (paso 3). Este script
  hace un "upsert": si el SKU ya existe, actualiza sus datos; si no,
  lo inserta. Nunca borra.

CÓMO CORRERLO:
    python migrar_catalogo_a_db.py

QUÉ HACE CON CAMPOS QUE NO ESTÁN EN EL JSON:
- precio: queda en NULL (el vendedor lo pondrá desde el panel admin).
- stock: queda en 0.
- activo: True.
- El resto (imagen_url, enfoque) se derivan del propio SKU y de la ruta
  convencional del catálogo.
"""

import os
import json

from database import SessionLocal, Base, engine
from models import Producto

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CATALOGO_JSON_PATH = os.path.join(BASE_DIR, "catalogo", "catalogo.json")


def deducir_enfoque(codigo_resultado: str) -> str:
    """CIN/CVE/COT/CPR -> colorimetria ; MRE/MCU/MDI/MOV -> morfologia."""
    if not codigo_resultado:
        return None
    prefijo = codigo_resultado[0].upper()
    if prefijo == "C":
        return "colorimetria"
    if prefijo == "M":
        return "morfologia"
    return None


def main():
    if not os.path.exists(CATALOGO_JSON_PATH):
        print(f"❌ No se encontró {CATALOGO_JSON_PATH}.")
        print("   Corre primero: python generar_catalogo_json.py")
        return

    # Por si las tablas todavía no existen (ej. si corres esto sin haber
    # arrancado el servidor antes), las creamos aquí también. Es idempotente.
    Base.metadata.create_all(bind=engine)

    with open(CATALOGO_JSON_PATH, "r", encoding="utf-8") as f:
        catalogo = json.load(f)

    print(f"📥 Cargando {len(catalogo)} SKUs desde catalogo.json...")

    db = SessionLocal()
    insertados = 0
    actualizados = 0
    saltados = 0

    try:
        for sku, info in catalogo.items():
            categoria = info.get("categoria")
            codigo = info.get("codigo")
            descripcion = info.get("descripcion") or sku
            enfoque = info.get("enfoque") or deducir_enfoque(codigo)

            if not categoria or not codigo:
                print(f"  ⚠️  {sku}: falta categoria o codigo, se salta")
                saltados += 1
                continue

            imagen_url = f"/catalogo/{categoria}/{codigo}/{sku}.png"

            existente = db.query(Producto).filter(Producto.sku == sku).first()
            if existente:
                # Actualizar solo campos que vienen del catálogo — precio y
                # stock los deja tranquilos porque los administra el vendedor.
                existente.nombre = descripcion
                existente.categoria = categoria
                existente.codigo_resultado = codigo
                existente.enfoque = enfoque
                existente.imagen_url = imagen_url
                actualizados += 1
            else:
                nuevo = Producto(
                    sku=sku,
                    nombre=descripcion,
                    categoria=categoria,
                    codigo_resultado=codigo,
                    enfoque=enfoque,
                    imagen_url=imagen_url,
                    precio=None,   # el vendedor lo pondrá desde el panel admin
                    stock=0,
                    activo=True,
                )
                db.add(nuevo)
                insertados += 1

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"❌ Error en la migración, se revirtió todo: {e}")
        raise
    finally:
        db.close()

    print()
    print(f"✅ Migración terminada.")
    print(f"   Insertados:   {insertados}")
    print(f"   Actualizados: {actualizados}")
    print(f"   Saltados:     {saltados}")
    print(f"   BD generada en: {os.path.join(BASE_DIR, 'lumiii.db')}")


if __name__ == "__main__":
    main()

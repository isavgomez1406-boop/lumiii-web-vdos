"""
Configuración de la base de datos de LUMIII.

Usamos SQLite en un archivo local (lumiii.db) porque:
- Viene incluido con Python, no necesita servidor aparte.
- Es perfecto para desarrollo en localhost.
- Cuando llegue el momento de subir a la nube, solo hay que cambiar
  la cadena de conexión de sqlite:/// a postgresql:///, y todo el
  código de modelos y consultas sigue igual (esa es la gracia de SQLAlchemy).

Este archivo expone 3 cosas que usa el resto del proyecto:
- engine       -> conexión física a la BD
- SessionLocal -> fábrica de sesiones para hacer consultas
- Base         -> clase base de la que heredan los modelos (ver models.py)

Y una utilidad:
- get_db()     -> dependencia para inyectar una sesión en endpoints de FastAPI
                  (se usará en el paso 2 y siguientes; por ahora está lista)
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RUTA_BD = os.path.join(BASE_DIR, "lumiii.db")

# Si existe la variable DATABASE_URL (ej. en Render conectado a Supabase), la usamos.
# Si no está definida, usamos la base SQLite local (lumiii.db).
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{RUTA_BD}")

# Supabase y otros servicios a menudo entregan la URL como postgres://...
# SQLAlchemy 2.0+ requiere que comience con postgresql://...
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# check_same_thread=False solo aplica para SQLite
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_engine(DATABASE_URL)

# Cada request va a abrir su propia Session, hacer sus consultas, y cerrarla.
# autoflush/autocommit en False = tú controlas explícitamente cuándo se
# escribe (con session.commit()), que es lo que quieres en un backend.
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# Todos los modelos (Usuario, Producto, HistorialAnalisis) heredan de esta
# Base. Cuando llamemos Base.metadata.create_all(bind=engine), SQLAlchemy
# crea las tablas que aún no existen en la BD.
Base = declarative_base()


def get_db():
    """
    Dependencia de FastAPI: entrega una sesión abierta al endpoint y la
    cierra al terminar (aunque el endpoint reviente por una excepción).
    Se usa así en un endpoint:

        @app.get("/algo")
        def algo(db: Session = Depends(get_db)):
            return db.query(Producto).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

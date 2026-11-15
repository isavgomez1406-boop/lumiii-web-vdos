"""
Modelos de la base de datos de LUMIII.

Tablas:
1. Usuario           -> cliente registrado; puede ser admin si es_admin=True
2. Producto          -> el catálogo real (llenado por migración y panel admin)
3. HistorialAnalisis -> registro de cada análisis hecho por un usuario logueado
4. Sesion            -> sesión activa (token) de un usuario logueado
                        (paso 3: reemplaza los tokens de admin en memoria por
                        sesiones persistentes en BD)
5. Interes           -> registro de cada clic en "Me interesa" sobre un modelo
                        (NUEVA en el paso 4)
"""

from datetime import datetime, timedelta
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime,
    ForeignKey, Text,
)
from sqlalchemy.orm import relationship

from database import Base


# ============================================================
#  USUARIOS
# ============================================================

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(120), nullable=False)
    correo = Column(String(160), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    es_admin = Column(Boolean, default=False, nullable=False)
    creado_en = Column(DateTime, default=datetime.utcnow, nullable=False)

    historial = relationship(
        "HistorialAnalisis",
        back_populates="usuario",
        cascade="all, delete-orphan",
    )
    sesiones = relationship(
        "Sesion",
        back_populates="usuario",
        cascade="all, delete-orphan",
    )
    intereses = relationship(
        "Interes",
        back_populates="usuario",
        cascade="all, delete-orphan",
    )

    def como_dict(self):
        """Datos seguros para enviar al frontend (sin password_hash)."""
        return {
            "id": self.id,
            "nombre": self.nombre,
            "correo": self.correo,
            "es_admin": self.es_admin,
        }

    def __repr__(self):
        return f"<Usuario id={self.id} correo={self.correo} admin={self.es_admin}>"


# ============================================================
#  PRODUCTOS (CATÁLOGO)
# ============================================================

class Producto(Base):
    __tablename__ = "productos"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(40), nullable=False, unique=True, index=True)
    nombre = Column(String(200), nullable=False)
    categoria = Column(String(40), nullable=False, index=True)
    codigo_resultado = Column(String(10), nullable=False, index=True)
    enfoque = Column(String(100), nullable=True)

    precio = Column(Float, nullable=True)
    stock = Column(Integer, default=0, nullable=False)

    imagen_url = Column(String(255), nullable=False)
    activo = Column(Boolean, default=True, nullable=False)

    creado_en = Column(DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    def como_dict(self):
        return {
            "sku": self.sku,
            "descripcion": self.nombre,
            "categoria": self.categoria,
            "codigo": self.codigo_resultado,
            "enfoque": self.enfoque,
            "precio": self.precio,
            "stock": self.stock,
            "imagen_url": self.imagen_url,
            "activo": self.activo,
        }

    def __repr__(self):
        return f"<Producto sku={self.sku} categoria={self.categoria} codigo={self.codigo_resultado}>"


# ============================================================
#  HISTORIAL DE ANÁLISIS
# ============================================================

class HistorialAnalisis(Base):
    __tablename__ = "historial_analisis"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(
        Integer,
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    morfologia_resultado = Column(String(40), nullable=True)
    estacion_resultado = Column(String(40), nullable=True)
    skus_recomendados = Column(Text, nullable=True)  # JSON serializado
    fecha = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    usuario = relationship("Usuario", back_populates="historial")

    def __repr__(self):
        return (
            f"<HistorialAnalisis id={self.id} usuario_id={self.usuario_id} "
            f"morfologia={self.morfologia_resultado} estacion={self.estacion_resultado}>"
        )


# ============================================================
#  SESIONES DE USUARIO (paso 3)
# ============================================================

def _dentro_de_30_dias():
    """Función auxiliar para el default del expira_en."""
    return datetime.utcnow() + timedelta(days=30)


class Sesion(Base):
    """
    Cada sesión = un token activo para un usuario logueado.

    Ventajas de guardar las sesiones en la BD (vs. tenerlas solo en memoria):
    - Sobreviven al reinicio del servidor: si el usuario ya está logueado,
      sigue estándolo aunque tumbes uvicorn.
    - Se pueden revocar individualmente (cerrar sesión en un dispositivo
      específico) borrando la fila correspondiente.
    - Cuando quieras "cerrar todas las sesiones de un usuario" (ej. cambió
      contraseña), es un DELETE con WHERE usuario_id=X.
    """
    __tablename__ = "sesiones"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(120), nullable=False, unique=True, index=True)
    usuario_id = Column(
        Integer,
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    creada_en = Column(DateTime, default=datetime.utcnow, nullable=False)
    expira_en = Column(DateTime, default=_dentro_de_30_dias, nullable=False)

    usuario = relationship("Usuario", back_populates="sesiones")

    def esta_vigente(self) -> bool:
        return datetime.utcnow() < self.expira_en

    def __repr__(self):
        return f"<Sesion id={self.id} usuario_id={self.usuario_id} expira={self.expira_en}>"


# ============================================================
#  INTERESES ("Me interesa" — paso 4)
# ============================================================

class Interes(Base):
    """
    Una fila = un clic en "Me interesa" sobre un modelo recomendado.
    No es un carrito (no hay cantidad ni checkout) — es una señal de interés
    que queda guardada para que, más adelante, tú (o el panel admin) puedas
    ver qué productos generan más interés real por resultado de morfología
    o colorimetría.

    No se deduplica a propósito: si el mismo usuario le da "Me interesa" dos
    veces al mismo SKU en momentos distintos, quedan dos filas — es una señal
    de interés repetido, no un error.
    """
    __tablename__ = "intereses"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(
        Integer,
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku = Column(String(40), nullable=False, index=True)
    tipo_recomendacion = Column(String(20), nullable=False)  # "morfologia" | "colorimetria"
    fecha = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    usuario = relationship("Usuario", back_populates="intereses")

    def como_dict(self):
        return {
            "id": self.id,
            "sku": self.sku,
            "tipo_recomendacion": self.tipo_recomendacion,
            "fecha": self.fecha.isoformat(),
        }

    def __repr__(self):
        return f"<Interes id={self.id} usuario_id={self.usuario_id} sku={self.sku} tipo={self.tipo_recomendacion}>"

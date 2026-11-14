"""
Script interactivo para crear un usuario administrador de LUMIII.

CUÁNDO CORRERLO:
- La primera vez que arrancas el sistema completo del paso 3
  (después de instalar passlib con `pip install "passlib[bcrypt]"`).
- Cuando quieras agregar otro admin (ej. un socio).

CÓMO CORRERLO:
    python crear_admin.py

Te va a preguntar nombre, correo y contraseña. La contraseña no se muestra
mientras la escribes (por seguridad). El usuario se crea en lumiii.db
con el flag es_admin=True, y desde ese momento puedes iniciar sesión con
ese correo en http://localhost:8080/login.html y entrar al panel del vendedor.

SI YA EXISTE UN USUARIO CON ESE CORREO:
El script te pregunta si quieres promoverlo a admin (cambia es_admin=True
sin tocar su contraseña) o cancelar.
"""

import getpass
import re
import sys

import bcrypt

from database import Base, engine, SessionLocal
from models import Usuario

REGEX_CORREO = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def hashear_password(p: str) -> str:
    pwd_bytes = p.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def pedir(mensaje, validador=None, esconder=False):
    while True:
        valor = (getpass.getpass(mensaje) if esconder else input(mensaje)).strip()
        if not valor:
            print("  (no puede estar vacío)")
            continue
        if validador:
            error = validador(valor)
            if error:
                print(f"  ⚠️  {error}")
                continue
        return valor


def validar_correo(c):
    if not REGEX_CORREO.match(c):
        return "Formato de correo inválido."
    return None


def validar_password(p):
    if len(p) < 6:
        return "La contraseña debe tener al menos 6 caracteres."
    return None


def main():
    # Crear tablas si aún no existen (por si corres este script antes que el server)
    Base.metadata.create_all(bind=engine)

    print("=== Crear usuario administrador de LUMIII ===\n")

    nombre = pedir("Nombre completo: ")
    correo = pedir("Correo: ", validar_correo).lower()

    db = SessionLocal()
    try:
        existente = db.query(Usuario).filter(Usuario.correo == correo).first()

        if existente:
            print(f"\nYa existe un usuario con ese correo (id={existente.id}, es_admin={existente.es_admin}).")
            if existente.es_admin:
                print("Ya es admin. No hay nada que hacer.")
                return
            resp = input("¿Quieres promoverlo a admin? [s/N]: ").strip().lower()
            if resp != "s":
                print("Cancelado.")
                return
            existente.es_admin = True
            db.commit()
            print(f"\n✅ Usuario '{existente.correo}' promovido a admin.")
            return

        password = pedir("Contraseña (mínimo 6 caracteres): ", validar_password, esconder=True)
        confirmacion = pedir("Confirma la contraseña: ", esconder=True)
        if password != confirmacion:
            print("\n❌ Las contraseñas no coinciden. Vuelve a correr el script.")
            sys.exit(1)

        nuevo = Usuario(
            nombre=nombre,
            correo=correo,
            password_hash=hashear_password(password),
            es_admin=True,
        )
        db.add(nuevo)
        db.commit()
        db.refresh(nuevo)

        print(f"\n✅ Admin creado.")
        print(f"   id:     {nuevo.id}")
        print(f"   nombre: {nuevo.nombre}")
        print(f"   correo: {nuevo.correo}")
        print(f"\nAhora puedes ir a http://localhost:8080/login.html e iniciar sesión.")
    finally:
        db.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelado.")

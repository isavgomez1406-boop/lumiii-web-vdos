"""
Diagnóstico de login de LUMIII.

Corre esto en la misma carpeta donde está lumiii.db (junto a tu server.py):

    python diagnostico_login.py

Te va a pedir el correo con el que intentas iniciar sesión, y te muestra:
1. Si existe una cuenta con ese correo EXACTO (revisa espacios/mayúsculas).
2. Si quieres, te deja probar una contraseña contra el hash guardado, para
   confirmar si el problema es "contraseña incorrecta" o algo más raro.

No modifica nada — solo lee y compara.
"""

import getpass
from database import SessionLocal
from models import Usuario
from passlib.hash import bcrypt


def main():
    print("=== Diagnóstico de login LUMIII ===\n")
    correo_input = input("Correo con el que intentas iniciar sesión: ").strip()
    correo_normalizado = correo_input.lower()

    if correo_input != correo_normalizado:
        print(f"\n⚠️  Ojo: escribiste '{correo_input}' pero el sistema lo normaliza a")
        print(f"    '{correo_normalizado}' antes de buscarlo (todo correo se guarda en minúsculas).")

    db = SessionLocal()
    try:
        # Búsqueda EXACTA (como lo hace el login real)
        usuario = db.query(Usuario).filter(Usuario.correo == correo_normalizado).first()

        if not usuario:
            print(f"\n❌ No hay ninguna cuenta con correo == '{correo_normalizado}' en lumiii.db.")

            # Buscar coincidencias parecidas para detectar typos/espacios
            parecidos = db.query(Usuario).filter(Usuario.correo.like(f"%{correo_normalizado.split('@')[0]}%")).all()
            if parecidos:
                print("\n   Pero encontré correos parecidos en la BD:")
                for u in parecidos:
                    print(f"   - '{u.correo}'  (¿tiene espacio, typo, o dominio distinto?)")
            else:
                print("   Tampoco encontré nada parecido. El registro puede no haberse guardado,")
                print("   o estás corriendo este script contra un lumiii.db distinto al del servidor.")
            return

        print(f"\n✅ Cuenta encontrada:")
        print(f"   id:          {usuario.id}")
        print(f"   nombre:      {usuario.nombre}")
        print(f"   correo:      {usuario.correo}")
        print(f"   es_admin:    {usuario.es_admin}")
        print(f"   creado_en:   {usuario.creado_en}")
        print(f"   hash guardado empieza con: {usuario.password_hash[:15]}...")

        if not usuario.password_hash.startswith("$2"):
            print("\n⚠️  El hash NO tiene el formato bcrypt esperado (debería empezar con $2b$ o $2a$).")
            print("    Si este usuario se insertó a mano (SQL directo) en vez de por /api/auth/registrar")
            print("    o crear_admin.py, el login siempre va a fallar aunque la contraseña sea correcta.")
            return

        probar = input("\n¿Quieres probar una contraseña contra este hash? [s/N]: ").strip().lower()
        if probar == "s":
            password = getpass.getpass("Contraseña a probar: ")
            if bcrypt.verify(password, usuario.password_hash):
                print("\n✅ La contraseña SÍ coincide con el hash guardado.")
                print("   Si el login real sigue fallando con esta misma combinación,")
                print("   el problema no es la contraseña — revisa la consola del servidor")
                print("   (uvicorn) para ver el traceback exacto del error.")
            else:
                print("\n❌ La contraseña NO coincide con el hash guardado.")
                print("   Esto confirma que es un problema de contraseña incorrecta")
                print("   (o el usuario se registró con otra contraseña / desde otra sesión de pruebas).")
    finally:
        db.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelado.")

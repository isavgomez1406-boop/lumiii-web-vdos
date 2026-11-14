document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('formRegistro');
    const mensaje = document.getElementById('mensajeRegistro');

    LumiiiAuth.usuarioActual().then((usuario) => {
        if (usuario) window.location.href = 'index.htm';
    });

    form.addEventListener('submit', async (ev) => {
        ev.preventDefault();
        mensaje.style.display = 'none';

        const datos = new FormData(form);
        const nombre = datos.get('nombre').trim();
        const correo = datos.get('correo').trim().toLowerCase();
        const password = datos.get('password');
        const confirmacion = datos.get('confirmacion');

        if (password !== confirmacion) {
            mensaje.className = 'mensaje-inline mensaje-error-inline';
            mensaje.innerText = '✗ Las contraseñas no coinciden.';
            mensaje.style.display = 'block';
            return;
        }

        const boton = form.querySelector('button[type="submit"]');
        boton.disabled = true;
        boton.innerText = 'Creando cuenta...';

        try {
            const usuario = await LumiiiAuth.registrar(nombre, correo, password);

            mensaje.className = 'mensaje-inline mensaje-exito';
            mensaje.innerText = `✓ Cuenta creada. Bienvenido, ${usuario.nombre.split(' ')[0]}.`;
            mensaje.style.display = 'block';

            setTimeout(() => { window.location.href = 'index.htm'; }, 700);
        } catch (e) {
            mensaje.className = 'mensaje-inline mensaje-error-inline';
            mensaje.innerText = '✗ ' + e.message;
            mensaje.style.display = 'block';
            boton.disabled = false;
            boton.innerText = 'Crear cuenta';
        }
    });
});

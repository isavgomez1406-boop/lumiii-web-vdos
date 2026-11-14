document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('formLogin');
    const mensaje = document.getElementById('mensajeLogin');

    // Si el usuario ya está logueado, mándalo al inicio
    LumiiiAuth.usuarioActual().then((usuario) => {
        if (usuario) window.location.href = 'index.htm';
    });

    form.addEventListener('submit', async (ev) => {
        ev.preventDefault();
        mensaje.style.display = 'none';

        const boton = form.querySelector('button[type="submit"]');
        boton.disabled = true;
        boton.innerText = 'Entrando...';

        try {
            const datos = new FormData(form);
            const correo = datos.get('correo').trim().toLowerCase();
            const password = datos.get('password');

            const usuario = await LumiiiAuth.login(correo, password);

            mensaje.className = 'mensaje-inline mensaje-exito';
            mensaje.innerText = `✓ Bienvenido, ${usuario.nombre.split(' ')[0]}. Redirigiendo...`;
            mensaje.style.display = 'block';

            // Si es admin, mándalo al panel; si no, al análisis
            setTimeout(() => {
                window.location.href = usuario.es_admin ? 'admin.html' : 'index.htm';
            }, 700);
        } catch (e) {
            mensaje.className = 'mensaje-inline mensaje-error-inline';
            mensaje.innerText = '✗ ' + e.message;
            mensaje.style.display = 'block';
            boton.disabled = false;
            boton.innerText = 'Entrar';
        }
    });
});

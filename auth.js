/*
 * auth.js — Biblioteca compartida de autenticación de LUMIII.
 *
 * Se carga en TODAS las páginas HTML (index, catalogo, conocimiento, admin,
 * login, registro). Hace dos cosas:
 *
 * 1. Expone el objeto global `LumiiiAuth` con métodos para login, registro,
 *    logout, obtener token y hacer fetch autenticado. Las otras páginas
 *    (login.js, registro.js, admin.js, script.js) lo usan en vez de repetir
 *    el mismo código de manejo de sesión en cada archivo.
 *
 * 2. Al cargarse, revisa si hay un usuario logueado (consulta /api/auth/actual)
 *    y actualiza dinámicamente la barra de navegación: si hay usuario, muestra
 *    "Hola, [Nombre]" + "Cerrar sesión" (+ link a Admin si es_admin); si no,
 *    muestra "Iniciar sesión" y "Registrarse".
 */

(function () {
    const URL_SERVIDOR = (window.location.origin && window.location.origin !== 'null' && !window.location.protocol.startsWith('file'))
        ? window.location.origin
        : 'http://localhost:8080';
    const CLAVE_TOKEN = 'lumiii_auth_token';

    const LumiiiAuth = {
        URL_SERVIDOR,

        obtenerToken() {
            return localStorage.getItem(CLAVE_TOKEN);
        },

        guardarToken(token) {
            localStorage.setItem(CLAVE_TOKEN, token);
        },

        borrarToken() {
            localStorage.removeItem(CLAVE_TOKEN);
        },

        // fetch con el header X-Auth-Token puesto automáticamente si hay sesión.
        // Si el server devuelve 401, borra el token localmente (sesión expirada).
        async fetch(url, opciones = {}) {
            const token = this.obtenerToken();
            const headers = { ...(opciones.headers || {}) };
            if (token) headers['X-Auth-Token'] = token;
            const resp = await fetch(url, { ...opciones, headers });
            if (resp.status === 401) {
                this.borrarToken();
            }
            return resp;
        },

        async registrar(nombre, correo, password) {
            const resp = await fetch(`${URL_SERVIDOR}/api/auth/registrar`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ nombre, correo, password }),
            });
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                throw new Error(err.detail || `Error ${resp.status}`);
            }
            const data = await resp.json();
            this.guardarToken(data.token);
            return data.usuario;
        },

        async login(correo, password) {
            const resp = await fetch(`${URL_SERVIDOR}/api/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ correo, password }),
            });
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                throw new Error(err.detail || `Error ${resp.status}`);
            }
            const data = await resp.json();
            this.guardarToken(data.token);
            return data.usuario;
        },

        async logout() {
            try {
                await this.fetch(`${URL_SERVIDOR}/api/auth/logout`, { method: 'POST' });
            } catch (_) { /* no importa */ }
            this.borrarToken();
        },

        async usuarioActual() {
            const token = this.obtenerToken();
            if (!token) return null;
            try {
                const resp = await this.fetch(`${URL_SERVIDOR}/api/auth/actual`);
                if (!resp.ok) return null;
                const data = await resp.json();
                return data.usuario;
            } catch (_) {
                return null;
            }
        },
    };

    window.LumiiiAuth = LumiiiAuth;

    // ============================================================
    //  Al cargar, actualizar la barra de navegación dinámicamente.
    // ============================================================

    document.addEventListener('DOMContentLoaded', async () => {
        const ul = document.querySelector('.navegacion ul');
        if (!ul) return;

        // Marcador para no duplicar items si el usuario navega en SPA-style
        if (ul.querySelector('[data-sesion]')) return;

        const usuario = await LumiiiAuth.usuarioActual();

        if (usuario) {
            // Link a Mis Favoritos
            const esPaginaFavoritos = window.location.pathname.includes('favoritos');
            const liFav = document.createElement('li');
            liFav.dataset.sesion = 'favoritos';
            liFav.innerHTML = `<a href="favoritos.html" class="${esPaginaFavoritos ? 'activo' : ''}">Mis Favoritos ❤️</a>`;
            ul.appendChild(liFav);

            // Link a Mi Perfil
            const esPaginaPerfil = window.location.pathname.includes('perfil');
            const liPerfil = document.createElement('li');
            liPerfil.dataset.sesion = 'perfil';
            liPerfil.innerHTML = `<a href="perfil.html" class="${esPaginaPerfil ? 'activo' : ''}">Mi Perfil 👤</a>`;
            ul.appendChild(liPerfil);

            // Si es admin, ofrecer link al panel (a menos que ya esté)
            if (usuario.es_admin && !ul.querySelector('a[href="admin.html"]')) {
                const esPaginaAdmin = window.location.pathname.includes('admin');
                const liAdmin = document.createElement('li');
                liAdmin.dataset.sesion = 'admin';
                liAdmin.innerHTML = `<a href="admin.html" class="${esPaginaAdmin ? 'activo' : ''}">Admin</a>`;
                ul.appendChild(liAdmin);
            }

            // "Hola, Nombre" (no link, solo saludo)
            const liSaludo = document.createElement('li');
            liSaludo.dataset.sesion = 'saludo';
            liSaludo.className = 'saludo-usuario';
            const primerNombre = (usuario.nombre || '').split(' ')[0];
            liSaludo.innerText = `Hola, ${primerNombre}`;
            ul.appendChild(liSaludo);

            // "Cerrar sesión"
            const liLogout = document.createElement('li');
            liLogout.dataset.sesion = 'logout';
            const a = document.createElement('a');
            a.href = '#';
            a.innerText = 'Cerrar sesión';
            a.addEventListener('click', async (ev) => {
                ev.preventDefault();
                await LumiiiAuth.logout();
                window.location.href = 'index.htm';
            });
            liLogout.appendChild(a);
            ul.appendChild(liLogout);
        } else {
            // Sin sesión → mostrar login + registro
            const liLogin = document.createElement('li');
            liLogin.dataset.sesion = 'login';
            liLogin.innerHTML = '<a href="login.html">Iniciar sesión</a>';
            ul.appendChild(liLogin);

            const liReg = document.createElement('li');
            liReg.dataset.sesion = 'registro';
            liReg.innerHTML = '<a href="registro.html" class="link-destacado">Registrarse</a>';
            ul.appendChild(liReg);
        }
    });
})();

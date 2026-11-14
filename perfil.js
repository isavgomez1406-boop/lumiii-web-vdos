document.addEventListener('DOMContentLoaded', async () => {
    const URL_SERVIDOR = LumiiiAuth.URL_SERVIDOR;

    // Elementos del DOM
    const vistaSinSesion = document.getElementById('vistaSinSesion');
    const vistaConSesion = document.getElementById('vistaConSesion');
    const textoCargando = document.getElementById('textoCargando');
    const textoError = document.getElementById('textoError');
    const contenidoPerfil = document.getElementById('contenidoPerfil');

    const avatarLetra = document.getElementById('avatarLetra');
    const nombreUsuario = document.getElementById('nombreUsuario');
    const badgeRol = document.getElementById('badgeRol');
    const correoUsuario = document.getElementById('correoUsuario');
    const fechaRegistro = document.getElementById('fechaRegistro');
    const contadorFavsPerfil = document.getElementById('contadorFavsPerfil');

    const bloqueConDiagnostico = document.getElementById('bloqueConDiagnostico');
    const bloqueSinDiagnostico = document.getElementById('bloqueSinDiagnostico');
    const fechaUltimoAnalisis = document.getElementById('fechaUltimoAnalisis');

    const resultadoMorfologiaPerfil = document.getElementById('resultadoMorfologiaPerfil');
    const asesoriaMorfologiaPerfil = document.getElementById('asesoriaMorfologiaPerfil');
    const resultadoEstacionPerfil = document.getElementById('resultadoEstacionPerfil');
    const asesoriaEstacionPerfil = document.getElementById('asesoriaEstacionPerfil');
    const galeriaRecomendadosPerfil = document.getElementById('galeriaRecomendadosPerfil');
    const cuerpoHistorialPerfil = document.getElementById('cuerpoHistorialPerfil');

    // ============================================================
    //  1. Verificar Sesión
    // ============================================================
    const usuario = await LumiiiAuth.usuarioActual();
    if (!usuario) {
        vistaSinSesion.style.display = 'block';
        vistaConSesion.style.display = 'none';
        return;
    }

    vistaSinSesion.style.display = 'none';
    vistaConSesion.style.display = 'block';

    // ============================================================
    //  2. Cargar Datos de Perfil desde /api/usuario/perfil
    // ============================================================
    async function cargarPerfil() {
        textoCargando.style.display = 'block';
        textoError.style.display = 'none';
        contenidoPerfil.style.display = 'none';

        try {
            const resp = await LumiiiAuth.fetch(`${URL_SERVIDOR}/api/usuario/perfil`);
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                throw new Error(err.detail || `Error HTTP ${resp.status}`);
            }

            const data = await resp.json();
            renderizarPerfil(data);
        } catch (e) {
            textoCargando.style.display = 'none';
            textoError.innerText = 'No se pudo cargar tu perfil: ' + e.message;
            textoError.style.display = 'block';
        }
    }

    // ============================================================
    //  3. Renderizar Vista de Perfil
    // ============================================================
    function renderizarPerfil(data) {
        textoCargando.style.display = 'none';
        contenidoPerfil.style.display = 'block';

        const u = data.usuario;
        const nombre = u.nombre || 'Usuario';
        nombreUsuario.innerText = nombre;
        avatarLetra.innerText = nombre.charAt(0).toUpperCase();
        correoUsuario.innerText = u.correo || '—';

        if (u.es_admin) {
            badgeRol.innerText = '👑 Administrador';
            badgeRol.className = 'badge-rol badge-rol-admin';
        } else {
            badgeRol.innerText = '🛍️ Cliente';
            badgeRol.className = 'badge-rol badge-rol-cliente';
        }

        if (u.creado_en) {
            const fechaReg = new Date(u.creado_en).toLocaleDateString('es-ES', {
                year: 'numeric', month: 'long', day: 'numeric'
            });
            fechaRegistro.innerText = `Miembro desde el ${fechaReg}`;
        } else {
            fechaRegistro.innerText = 'Miembro de LUMIII';
        }

        contadorFavsPerfil.innerText = data.total_intereses || 0;

        // Diagnóstico Permanente
        const diag = data.diagnostico_permanente;
        if (diag) {
            bloqueConDiagnostico.style.display = 'block';
            bloqueSinDiagnostico.style.display = 'none';

            const fDiag = new Date(diag.fecha).toLocaleDateString('es-ES', {
                year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
            });
            fechaUltimoAnalisis.innerText = fDiag;

            resultadoMorfologiaPerfil.innerText = `${diag.morfologia} (${diag.codigo_morfologia})`;
            asesoriaMorfologiaPerfil.innerText = diag.asesoria_morfologia || 'Sin asesoría registrada.';

            resultadoEstacionPerfil.innerText = `${diag.estacion} (${diag.codigo_estacion})`;
            asesoriaEstacionPerfil.innerText = diag.asesoria_estacion || 'Sin asesoría registrada.';

            // Renderizar Modelos Recomendados Fijos
            galeriaRecomendadosPerfil.innerHTML = '';
            const todosModelos = [];

            // Extraer modelos de morfología y colorimetría
            [diag.modelos_morfologia, diag.modelos_colorimetria].forEach((grupo, idx) => {
                const tipo = idx === 0 ? 'morfologia' : 'colorimetria';
                if (!grupo) return;
                Object.values(grupo).forEach((lista) => {
                    lista.forEach((m) => todosModelos.push({ ...m, tipo_rec: tipo }));
                });
            });

            if (todosModelos.length === 0) {
                galeriaRecomendadosPerfil.innerHTML = '<p class="sin-modelos">No hay modelos asociados directamente en el catálogo.</p>';
            } else {
                todosModelos.slice(0, 10).forEach((modelo) => {
                    galeriaRecomendadosPerfil.appendChild(crearTarjetaModeloPerfil(modelo));
                });
            }

        } else {
            bloqueConDiagnostico.style.display = 'none';
            bloqueSinDiagnostico.style.display = 'block';
        }

        // Historial de Diagnósticos Previos
        cuerpoHistorialPerfil.innerHTML = '';
        if (!data.historial_analisis || data.historial_analisis.length === 0) {
            cuerpoHistorialPerfil.innerHTML = '<tr><td colspan="3" class="sin-modelos" style="padding: 20px; text-align: center;">Aún no tienes análisis previos registrados.</td></tr>';
        } else {
            data.historial_analisis.forEach((h) => {
                const fila = document.createElement('tr');
                const fechaFormat = new Date(h.fecha).toLocaleString('es-ES', {
                    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'
                });
                fila.innerHTML = `
                    <td style="font-size: 13.5px; color: var(--tinta-suave); font-weight: 600;">${fechaFormat}</td>
                    <td><span class="badge-morfologia" style="display:inline-block; padding: 4px 10px; border-radius: 6px; font-weight: 700;">${h.morfologia || '—'}</span></td>
                    <td><span class="badge-colorimetria" style="display:inline-block; padding: 4px 10px; border-radius: 6px; font-weight: 700;">${h.estacion || '—'}</span></td>
                `;
                cuerpoHistorialPerfil.appendChild(fila);
            });
        }
    }

    // ============================================================
    //  4. Crear Tarjeta de Modelo en Perfil
    // ============================================================
    function crearTarjetaModeloPerfil(modelo) {
        const tarjeta = document.createElement('div');
        tarjeta.className = 'tarjeta-modelo-perfil';

        const img = document.createElement('img');
        img.src = URL_SERVIDOR + modelo.imagen_url;
        img.alt = modelo.descripcion || modelo.sku;
        img.loading = 'lazy';
        img.onerror = () => { tarjeta.style.display = 'none'; };

        const descripcion = document.createElement('p');
        descripcion.className = 'desc-modelo-perfil';
        descripcion.innerText = modelo.descripcion || modelo.sku;

        const btnInteres = document.createElement('button');
        btnInteres.type = 'button';
        btnInteres.className = 'boton-me-interesa';
        btnInteres.innerText = '♡ Me interesa';
        btnInteres.addEventListener('click', () => marcarInteresPerfil(modelo.sku, modelo.tipo_rec, btnInteres));

        tarjeta.appendChild(img);
        tarjeta.appendChild(descripcion);
        tarjeta.appendChild(btnInteres);
        return tarjeta;
    }

    async function marcarInteresPerfil(sku, tipoRec, boton) {
        boton.disabled = true;
        boton.innerText = 'Guardando...';
        try {
            const resp = await LumiiiAuth.fetch(`${URL_SERVIDOR}/api/interes`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sku, tipo_recomendacion: tipoRec || 'colorimetria' }),
            });
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                throw new Error(err.detail || `HTTP ${resp.status}`);
            }
            boton.innerText = '❤ Guardado';
            boton.classList.add('guardado');
            // Incrementar contador de favs
            contadorFavsPerfil.innerText = Number(contadorFavsPerfil.innerText || 0) + 1;
        } catch (e) {
            boton.disabled = false;
            boton.innerText = '♡ Me interesa';
            alert('No se pudo guardar: ' + e.message);
        }
    }

    // Carga inicial
    cargarPerfil();
});

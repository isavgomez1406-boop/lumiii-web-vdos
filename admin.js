document.addEventListener('DOMContentLoaded', async () => {
    const URL_SERVIDOR = LumiiiAuth.URL_SERVIDOR;

    // Elementos del DOM de permisos y vistas
    const mensajeCargandoPermisos = document.getElementById('mensajeCargandoPermisos');
    const mensajeSinPermisos = document.getElementById('mensajeSinPermisos');
    const vistaPanel = document.getElementById('vistaPanel');

    // Pestañas
    const botonesPestana = document.querySelectorAll('.pestana-admin');
    const seccionEstadisticas = document.getElementById('seccionEstadisticas');
    const seccionCatalogo = document.getElementById('seccionCatalogo');

    // Elementos de Estadísticas
    const cargandoStats = document.getElementById('cargandoStats');
    const errorStats = document.getElementById('errorStats');
    const contenidoStats = document.getElementById('contenidoStats');

    const kpiUsuarios = document.getElementById('kpiUsuarios');
    const kpiAnalisis = document.getElementById('kpiAnalisis');
    const kpiIntereses = document.getElementById('kpiIntereses');
    const kpiProductos = document.getElementById('kpiProductos');

    const cuerpoTopProductos = document.getElementById('cuerpoTopProductos');
    const graficaMorfologia = document.getElementById('graficaMorfologia');
    const tipMorfologia = document.getElementById('tipMorfologia');
    const graficaColorimetria = document.getElementById('graficaColorimetria');
    const tipColorimetria = document.getElementById('tipColorimetria');
    const gridCategoriasInteres = document.getElementById('gridCategoriasInteres');
    const cuerpoActividadReciente = document.getElementById('cuerpoActividadReciente');

    // Elementos de Catálogo
    const formNuevoProducto = document.getElementById('formNuevoProducto');
    const mensajeNuevoProducto = document.getElementById('mensajeNuevoProducto');
    const filtroCategoria = document.getElementById('filtroCategoria');
    const filtroCodigo = document.getElementById('filtroCodigo');
    const filtroSoloActivos = document.getElementById('filtroSoloActivos');
    const contadorProductos = document.getElementById('contadorProductos');
    const mensajeCargando = document.getElementById('mensajeCargando');
    const mensajeErrorTabla = document.getElementById('mensajeErrorTabla');
    const tablaProductos = document.getElementById('tablaProductos');
    const cuerpoTabla = document.getElementById('cuerpoTabla');

    let productos = [];

    // ============================================================
    //  1. Guardián de acceso: solo admins entran
    // ============================================================
    const usuario = await LumiiiAuth.usuarioActual();
    if (!usuario) {
        window.location.href = 'login.html';
        return;
    }
    if (!usuario.es_admin) {
        mensajeCargandoPermisos.style.display = 'none';
        mensajeSinPermisos.style.display = 'block';
        return;
    }

    mensajeCargandoPermisos.style.display = 'none';
    vistaPanel.style.display = 'block';

    // ============================================================
    //  2. Alternar pestañas (Estadísticas <-> Catálogo)
    // ============================================================
    botonesPestana.forEach((boton) => {
        boton.addEventListener('click', () => {
            botonesPestana.forEach((b) => b.classList.remove('activa'));
            boton.classList.add('activa');

            const seccion = boton.dataset.seccion;
            if (seccion === 'estadisticas') {
                seccionEstadisticas.style.display = 'block';
                seccionCatalogo.style.display = 'none';
                cargarEstadisticas();
            } else {
                seccionEstadisticas.style.display = 'none';
                seccionCatalogo.style.display = 'block';
                cargarProductos();
            }
        });
    });

    // ============================================================
    //  3. DASHBOARD DE ESTADÍSTICAS Y DEMANDA
    // ============================================================
    async function cargarEstadisticas() {
        cargandoStats.style.display = 'block';
        errorStats.style.display = 'none';
        contenidoStats.style.display = 'none';

        try {
            const resp = await LumiiiAuth.fetch(`${URL_SERVIDOR}/api/admin/estadisticas`);
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                throw new Error(err.detail || `Error HTTP ${resp.status}`);
            }

            const data = await resp.json();
            renderizarEstadisticas(data);
        } catch (e) {
            cargandoStats.style.display = 'none';
            errorStats.innerText = 'No se pudieron cargar las estadísticas: ' + e.message;
            errorStats.style.display = 'block';
        }
    }

    function renderizarEstadisticas(data) {
        cargandoStats.style.display = 'none';
        contenidoStats.style.display = 'block';

        // 1. KPIs
        kpiUsuarios.innerText = data.kpis.total_usuarios || 0;
        kpiAnalisis.innerText = data.kpis.total_analisis || 0;
        kpiIntereses.innerText = data.kpis.total_intereses || 0;
        kpiProductos.innerText = `${data.kpis.total_activos || 0} / ${data.kpis.total_productos || 0}`;

        // 2. Top 10 Productos Más Deseados
        cuerpoTopProductos.innerHTML = '';
        if (!data.top_productos || data.top_productos.length === 0) {
            cuerpoTopProductos.innerHTML = '<tr><td colspan="7" class="sin-modelos" style="padding: 20px; text-align: center;">Aún no se registran intenciones de compra.</td></tr>';
        } else {
            const maxDeseos = Math.max(...data.top_productos.map((p) => p.total_deseos), 1);
            data.top_productos.forEach((p, idx) => {
                const fila = document.createElement('tr');
                const pct = Math.round((p.total_deseos / maxDeseos) * 100);

                fila.innerHTML = `
                    <td><img src="${URL_SERVIDOR + p.imagen_url}" alt="${p.sku}" class="thumb-producto" onerror="this.style.opacity='0.2'"></td>
                    <td class="celda-sku"><strong>#${idx + 1}</strong> ${p.sku}</td>
                    <td>${p.nombre}</td>
                    <td><span class="badge-categoria">${p.categoria}</span></td>
                    <td><strong>${p.codigo}</strong></td>
                    <td style="font-weight: 700; color: var(--violeta);">${p.precio != null ? '$' + Number(p.precio).toFixed(2) : '—'}</td>
                    <td>
                        <div class="barra-progreso-wrap">
                            <div class="barra-progreso" style="width: ${pct}%;"></div>
                            <span class="texto-progreso">${p.total_deseos} ❤️</span>
                        </div>
                    </td>
                `;
                cuerpoTopProductos.appendChild(fila);
            });
        }

        // 3. Distribución de Morfología
        renderizarGraficaBarras(
            graficaMorfologia,
            tipMorfologia,
            data.distribucion_morfologia,
            'morfologia',
            'forma de rostro'
        );

        // 4. Distribución de Colorimetría
        renderizarGraficaBarras(
            graficaColorimetria,
            tipColorimetria,
            data.distribucion_colorimetria,
            'colorimetria',
            'estación de color'
        );

        // 5. Demanda por Categoría
        gridCategoriasInteres.innerHTML = '';
        const categorias = data.intereses_por_categoria || {};
        const totalInteresesCat = Object.values(categorias).reduce((a, b) => a + b, 0) || 1;

        const iconosCat = {
            lentes: '👓',
            bufandas: '🧣',
            cintillo: '🎀',
            chaqueta: '🧥',
            franelas: '👕',
        };

        Object.entries(categorias).forEach(([cat, conteo]) => {
            const card = document.createElement('div');
            card.className = 'tarjeta-categoria-stat';
            const pct = Math.round((conteo / totalInteresesCat) * 100);

            card.innerHTML = `
                <div class="icono-cat-stat">${iconosCat[cat] || '🛍️'}</div>
                <div class="nombre-cat-stat">${cat.toUpperCase()}</div>
                <div class="valor-cat-stat">${conteo} <span>favoritos</span></div>
                <div class="barra-cat-wrap">
                    <div class="barra-cat" style="width: ${pct}%;"></div>
                </div>
                <small class="sub-cat-stat">${pct}% de la demanda</small>
            `;
            gridCategoriasInteres.appendChild(card);
        });

        // 6. Actividad Reciente
        cuerpoActividadReciente.innerHTML = '';
        if (!data.actividad_reciente || data.actividad_reciente.length === 0) {
            cuerpoActividadReciente.innerHTML = '<tr><td colspan="4" class="sin-modelos" style="padding: 20px; text-align: center;">No hay análisis registrados todavía.</td></tr>';
        } else {
            data.actividad_reciente.forEach((a) => {
                const fila = document.createElement('tr');
                const fechaFormat = new Date(a.fecha).toLocaleString('es-ES', {
                    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
                });
                fila.innerHTML = `
                    <td style="font-size: 13px; color: var(--tinta-suave);">${fechaFormat}</td>
                    <td><strong>${a.usuario}</strong> <small style="color: var(--tinta-suave);">(${a.correo})</small></td>
                    <td><span class="badge-morfologia" style="display:inline-block; padding: 4px 8px; border-radius: 6px; font-weight: 700;">${a.morfologia || '—'}</span></td>
                    <td><span class="badge-colorimetria" style="display:inline-block; padding: 4px 8px; border-radius: 6px; font-weight: 700;">${a.estacion || '—'}</span></td>
                `;
                cuerpoActividadReciente.appendChild(fila);
            });
        }
    }

    function renderizarGraficaBarras(contenedor, contenedorTip, datosObj, tipo, nombreMetrica) {
        contenedor.innerHTML = '';
        contenedorTip.innerHTML = '';

        const entradas = Object.entries(datosObj || {});
        if (entradas.length === 0) {
            contenedor.innerHTML = '<p class="sin-modelos">Sin suficientes datos de análisis aún.</p>';
            return;
        }

        const total = entradas.reduce((sum, [, val]) => sum + val, 0);
        let lider = { nombre: '', total: -1 };

        entradas.sort((a, b) => b[1] - a[1]);

        entradas.forEach(([clave, valor]) => {
            if (valor > lider.total) lider = { nombre: clave, total: valor };
            const pct = Math.round((valor / total) * 100);

            const filaBarra = document.createElement('div');
            filaBarra.className = 'fila-barra-stat';

            let colorBarra = 'var(--violeta)';
            if (tipo === 'colorimetria') {
                if (clave === 'Invierno') colorBarra = 'var(--invierno)';
                else if (clave === 'Verano') colorBarra = 'var(--verano)';
                else if (clave === 'Otoño') colorBarra = 'var(--otono)';
                else if (clave === 'Primavera') colorBarra = 'var(--primavera)';
            } else {
                if (clave === 'Ovalado') colorBarra = 'var(--forma-ovalado)';
                else if (clave === 'Redondo') colorBarra = 'var(--forma-redondo)';
                else if (clave === 'Cuadrado') colorBarra = 'var(--forma-cuadrado)';
                else if (clave === 'Diamante') colorBarra = 'var(--forma-diamante)';
            }

            filaBarra.innerHTML = `
                <div class="info-barra">
                    <span class="nombre-barra"><strong>${clave}</strong></span>
                    <span class="valor-barra">${valor} (${pct}%)</span>
                </div>
                <div class="track-barra">
                    <div class="fill-barra" style="width: ${pct}%; background-color: ${colorBarra};"></div>
                </div>
            `;
            contenedor.appendChild(filaBarra);
        });

        // Generar Insight inteligente para el negocio
        const pctLider = Math.round((lider.total / total) * 100);
        contenedorTip.innerHTML = `
            <div class="icono-insight">💡</div>
            <div>
                <strong>Insight de Demanda:</strong> El <strong>${pctLider}%</strong> de tus clientes pertenecen a <em>"${lider.nombre}"</em>. 
                Prioriza y mantén mayor stock de prendas con este código en tu catálogo comercial.
            </div>
        `;
    }

    // ============================================================
    //  4. GESTIÓN DE CATÁLOGO (CRUD DE PRODUCTOS)
    // ============================================================
    async function cargarProductos() {
        mensajeCargando.style.display = 'block';
        mensajeErrorTabla.style.display = 'none';
        tablaProductos.style.display = 'none';

        try {
            const resp = await LumiiiAuth.fetch(`${URL_SERVIDOR}/api/admin/productos`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            productos = await resp.json();
            pintarTabla();
        } catch (e) {
            mensajeCargando.style.display = 'none';
            mensajeErrorTabla.innerText = 'No se pudieron cargar los productos: ' + e.message;
            mensajeErrorTabla.style.display = 'block';
        }
    }

    function pintarTabla() {
        const catFiltro = filtroCategoria.value;
        const codFiltro = filtroCodigo.value;
        const soloActivos = filtroSoloActivos.checked;

        const filtrados = productos.filter((p) => {
            if (catFiltro && p.categoria !== catFiltro) return false;
            if (codFiltro && p.codigo !== codFiltro) return false;
            if (soloActivos && !p.activo) return false;
            return true;
        });

        contadorProductos.innerText = `${filtrados.length} de ${productos.length}`;
        cuerpoTabla.innerHTML = '';
        filtrados.forEach((p) => cuerpoTabla.appendChild(crearFila(p)));
        mensajeCargando.style.display = 'none';
        tablaProductos.style.display = 'table';
    }

    function crearFila(p) {
        const fila = document.createElement('tr');
        fila.dataset.sku = p.sku;
        if (!p.activo) fila.classList.add('fila-inactiva');

        const celImg = document.createElement('td');
        const img = document.createElement('img');
        img.src = URL_SERVIDOR + p.imagen_url;
        img.alt = p.sku;
        img.className = 'thumb-producto';
        img.loading = 'lazy';
        img.onerror = () => { img.style.opacity = '0.2'; };
        celImg.appendChild(img);
        fila.appendChild(celImg);

        const celSku = document.createElement('td');
        celSku.innerText = p.sku;
        celSku.className = 'celda-sku';
        fila.appendChild(celSku);

        const celNombre = document.createElement('td');
        const inputNombre = document.createElement('input');
        inputNombre.type = 'text';
        inputNombre.value = p.nombre || p.descripcion || '';
        inputNombre.className = 'input-tabla input-nombre';
        inputNombre.dataset.campo = 'nombre';
        celNombre.appendChild(inputNombre);
        fila.appendChild(celNombre);

        const celCat = document.createElement('td');
        celCat.innerText = p.categoria;
        fila.appendChild(celCat);

        const celCod = document.createElement('td');
        celCod.innerText = p.codigo;
        fila.appendChild(celCod);

        const celPrecio = document.createElement('td');
        const inputPrecio = document.createElement('input');
        inputPrecio.type = 'number';
        inputPrecio.step = '0.01';
        inputPrecio.min = '0';
        inputPrecio.value = p.precio ?? '';
        inputPrecio.placeholder = '—';
        inputPrecio.className = 'input-tabla input-precio';
        inputPrecio.dataset.campo = 'precio';
        celPrecio.appendChild(inputPrecio);
        fila.appendChild(celPrecio);

        const celStock = document.createElement('td');
        const inputStock = document.createElement('input');
        inputStock.type = 'number';
        inputStock.min = '0';
        inputStock.value = p.stock ?? 0;
        inputStock.className = 'input-tabla input-stock';
        inputStock.dataset.campo = 'stock';
        celStock.appendChild(inputStock);
        fila.appendChild(celStock);

        const celActivo = document.createElement('td');
        const checkActivo = document.createElement('input');
        checkActivo.type = 'checkbox';
        checkActivo.checked = !!p.activo;
        checkActivo.dataset.campo = 'activo';
        celActivo.appendChild(checkActivo);
        fila.appendChild(celActivo);

        const celAcciones = document.createElement('td');
        celAcciones.className = 'celda-acciones';

        const btnGuardar = document.createElement('button');
        btnGuardar.type = 'button';
        btnGuardar.className = 'boton-mini';
        btnGuardar.innerText = 'Guardar';
        btnGuardar.addEventListener('click', () => guardarCambios(p.sku, fila, btnGuardar));
        celAcciones.appendChild(btnGuardar);

        const btnEliminar = document.createElement('button');
        btnEliminar.type = 'button';
        btnEliminar.className = 'boton-mini boton-peligro';
        btnEliminar.innerText = p.activo ? 'Desactivar' : 'Reactivar';
        btnEliminar.addEventListener('click', () => alternarActivo(p, btnEliminar));
        celAcciones.appendChild(btnEliminar);

        fila.appendChild(celAcciones);
        return fila;
    }

    [filtroCategoria, filtroCodigo].forEach((sel) => {
        sel.addEventListener('change', pintarTabla);
    });
    filtroSoloActivos.addEventListener('change', pintarTabla);

    async function guardarCambios(sku, fila, btn) {
        const cambios = {};
        fila.querySelectorAll('[data-campo]').forEach((el) => {
            const campo = el.dataset.campo;
            if (el.type === 'checkbox') {
                cambios[campo] = el.checked;
            } else if (el.type === 'number') {
                cambios[campo] = el.value === '' ? null : Number(el.value);
            } else {
                cambios[campo] = el.value;
            }
        });

        btn.disabled = true;
        btn.innerText = 'Guardando...';

        try {
            const resp = await LumiiiAuth.fetch(`${URL_SERVIDOR}/api/admin/productos/${sku}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(cambios),
            });

            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                throw new Error(err.detail || `HTTP ${resp.status}`);
            }

            const productoActualizado = await resp.json();
            const idx = productos.findIndex((p) => p.sku === sku);
            if (idx >= 0) productos[idx] = productoActualizado;

            btn.innerText = '✓ Guardado';
            fila.classList.toggle('fila-inactiva', !productoActualizado.activo);
            setTimeout(() => { btn.innerText = 'Guardar'; btn.disabled = false; }, 1200);
        } catch (e) {
            btn.innerText = '✗ Error';
            alert('No se pudo guardar: ' + e.message);
            setTimeout(() => { btn.innerText = 'Guardar'; btn.disabled = false; }, 1500);
        }
    }

    async function alternarActivo(producto, btn) {
        const nuevoActivo = !producto.activo;
        const accion = nuevoActivo ? 'reactivar' : 'desactivar';
        if (!confirm(`¿Seguro que quieres ${accion} "${producto.sku}"?`)) return;

        try {
            const resp = await LumiiiAuth.fetch(`${URL_SERVIDOR}/api/admin/productos/${producto.sku}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ activo: nuevoActivo }),
            });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            await cargarProductos();
        } catch (e) {
            alert('No se pudo cambiar el estado: ' + e.message);
        }
    }

    formNuevoProducto.addEventListener('submit', async (ev) => {
        ev.preventDefault();
        mensajeNuevoProducto.style.display = 'none';

        const formData = new FormData(formNuevoProducto);
        const boton = formNuevoProducto.querySelector('button[type="submit"]');
        boton.disabled = true;
        boton.innerText = 'Guardando...';

        try {
            const resp = await LumiiiAuth.fetch(`${URL_SERVIDOR}/api/admin/productos`, {
                method: 'POST',
                body: formData,
            });

            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                throw new Error(err.detail || `HTTP ${resp.status}`);
            }

            const nuevo = await resp.json();
            mensajeNuevoProducto.className = 'mensaje-inline mensaje-exito';
            mensajeNuevoProducto.innerText = `✓ Producto "${nuevo.sku}" agregado al catálogo.`;
            mensajeNuevoProducto.style.display = 'block';
            formNuevoProducto.reset();
            await cargarProductos();
        } catch (e) {
            mensajeNuevoProducto.className = 'mensaje-inline mensaje-error-inline';
            mensajeNuevoProducto.innerText = '✗ ' + e.message;
            mensajeNuevoProducto.style.display = 'block';
        } finally {
            boton.disabled = false;
            boton.innerText = 'Guardar producto';
        }
    });

    // Carga inicial: Estadísticas por defecto
    cargarEstadisticas();
});

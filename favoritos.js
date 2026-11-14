document.addEventListener('DOMContentLoaded', async () => {
    const URL_SERVIDOR = LumiiiAuth.URL_SERVIDOR;

    // ============================================================
    //  CONFIGURACIÓN COMERCIAL
    //  Coloca aquí tu número de WhatsApp con código de país (sin + ni espacios).
    //  Ejemplo Venezuela: '584121234567' | Ejemplo México: '5215512345678'
    // ============================================================
    const TELEFONO_WHATSAPP = '584262137545';

    // Elementos del DOM
    const vistaSinSesion = document.getElementById('vistaSinSesion');
    const vistaConSesion = document.getElementById('vistaConSesion');
    const textoCargando = document.getElementById('textoCargando');
    const textoError = document.getElementById('textoError');
    const bannerResumen = document.getElementById('bannerResumen');
    const contadorTotal = document.getElementById('contadorTotal');
    const montoTotal = document.getElementById('montoTotal');
    const btnPedirTodosWhatsApp = document.getElementById('btnPedirTodosWhatsApp');
    const vistaVacia = document.getElementById('vistaVacia');
    const grillaFavoritos = document.getElementById('grillaFavoritos');

    let usuario = null;
    let listaIntereses = [];

    // ============================================================
    //  1. Verificar Sesión
    // ============================================================
    usuario = await LumiiiAuth.usuarioActual();
    if (!usuario) {
        vistaSinSesion.style.display = 'block';
        vistaConSesion.style.display = 'none';
        return;
    }

    vistaSinSesion.style.display = 'none';
    vistaConSesion.style.display = 'block';

    // ============================================================
    //  2. Cargar Favoritos desde /api/mis-intereses
    // ============================================================
    async function cargarFavoritos() {
        textoCargando.style.display = 'block';
        textoError.style.display = 'none';
        bannerResumen.style.display = 'none';
        vistaVacia.style.display = 'none';
        grillaFavoritos.style.display = 'none';

        try {
            const resp = await LumiiiAuth.fetch(`${URL_SERVIDOR}/api/mis-intereses`);
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                throw new Error(err.detail || `Error HTTP ${resp.status}`);
            }

            listaIntereses = await resp.json();
            renderizarVista();
        } catch (e) {
            textoCargando.style.display = 'none';
            textoError.innerText = 'No se pudieron cargar tus favoritos: ' + e.message;
            textoError.style.display = 'block';
        }
    }

    // ============================================================
    //  3. Renderizar Vista y Totales
    // ============================================================
    function renderizarVista() {
        textoCargando.style.display = 'none';

        if (!listaIntereses || listaIntereses.length === 0) {
            bannerResumen.style.display = 'none';
            grillaFavoritos.style.display = 'none';
            vistaVacia.style.display = 'block';
            return;
        }

        vistaVacia.style.display = 'none';
        bannerResumen.style.display = 'flex';
        grillaFavoritos.style.display = 'grid';

        // Calcular totales
        const cantidad = listaIntereses.length;
        contadorTotal.innerText = `${cantidad} producto${cantidad > 1 ? 's' : ''} guardado${cantidad > 1 ? 's' : ''}`;

        let totalDinero = 0;
        let tienePrecios = false;
        listaIntereses.forEach((item) => {
            if (item.producto && item.producto.precio != null) {
                totalDinero += Number(item.producto.precio);
                tienePrecios = true;
            }
        });

        if (tienePrecios) {
            montoTotal.innerText = `Total estimado: $${totalDinero.toFixed(2)}`;
            montoTotal.style.display = 'block';
        } else {
            montoTotal.innerText = 'Precios a consultar con el asesor';
            montoTotal.style.display = 'block';
        }

        // Pintar tarjetas
        grillaFavoritos.innerHTML = '';
        listaIntereses.forEach((item) => {
            grillaFavoritos.appendChild(crearTarjetaFavorito(item));
        });
    }

    // ============================================================
    //  4. Crear Tarjeta Individual de Favorito
    // ============================================================
    function crearTarjetaFavorito(item) {
        const p = item.producto || {
            sku: item.sku,
            descripcion: item.sku,
            categoria: 'general',
            precio: null,
            imagen_url: ''
        };

        const tarjeta = document.createElement('div');
        tarjeta.className = 'tarjeta-favorito';
        tarjeta.dataset.id = item.id;

        // Imagen
        const contenedorImg = document.createElement('div');
        contenedorImg.className = 'contenedor-img-fav';
        const img = document.createElement('img');
        img.src = URL_SERVIDOR + (p.imagen_url || `/catalogo/${p.categoria}/${item.sku}.png`);
        img.alt = p.descripcion || item.sku;
        img.loading = 'lazy';
        img.onerror = () => { img.style.opacity = '0.3'; };
        contenedorImg.appendChild(img);
        tarjeta.appendChild(contenedorImg);

        // Contenido / Detalles
        const cuerpo = document.createElement('div');
        cuerpo.className = 'cuerpo-fav';

        const etiquetaTipo = document.createElement('span');
        etiquetaTipo.className = `badge-tipo badge-${item.tipo_recomendacion || 'general'}`;
        etiquetaTipo.innerText = item.tipo_recomendacion === 'morfologia' ? 'Recomendado por Morfología' : 'Recomendado por Colorimetría';
        cuerpo.appendChild(etiquetaTipo);

        const titulo = document.createElement('h3');
        titulo.className = 'titulo-fav';
        titulo.innerText = p.descripcion || item.sku;
        cuerpo.appendChild(titulo);

        const skuText = document.createElement('p');
        skuText.className = 'sku-fav';
        skuText.innerText = `SKU: ${item.sku} • Cat: ${p.categoria || '—'}`;
        cuerpo.appendChild(skuText);

        const precioText = document.createElement('p');
        precioText.className = 'precio-fav';
        precioText.innerText = p.precio != null ? `$${Number(p.precio).toFixed(2)}` : 'Precio a consultar';
        cuerpo.appendChild(precioText);

        // Botones de acción
        const acciones = document.createElement('div');
        acciones.className = 'acciones-fav';

        // Botón WhatsApp individual
        const btnWa = document.createElement('button');
        btnWa.type = 'button';
        btnWa.className = 'boton-whatsapp boton-whatsapp-mini';
        btnWa.innerHTML = '<span>📱</span> Pedir por WhatsApp';
        btnWa.addEventListener('click', () => pedirIndividualPorWhatsApp(item));
        acciones.appendChild(btnWa);

        // Botón Eliminar
        const btnEliminar = document.createElement('button');
        btnEliminar.type = 'button';
        btnEliminar.className = 'boton-eliminar-fav';
        btnEliminar.innerText = 'Quitar';
        btnEliminar.addEventListener('click', () => eliminarFavorito(item.id, tarjeta));
        acciones.appendChild(btnEliminar);

        cuerpo.appendChild(acciones);
        tarjeta.appendChild(cuerpo);
        return tarjeta;
    }

    // ============================================================
    //  5. Pedido Individual por WhatsApp
    // ============================================================
    function pedirIndividualPorWhatsApp(item) {
        const nombreCliente = (usuario.nombre || 'Cliente').trim();
        const p = item.producto || {};
        const precio = p.precio != null ? `$${Number(p.precio).toFixed(2)}` : 'a consultar';
        const descripcion = p.descripcion || item.sku;

        const mensaje = 
`Hola LUMIII!
Mi nombre es *${nombreCliente}*. Me hice el análisis en la plataforma y me interesa adquirir este producto recomendado:
 
 *Producto:* ${descripcion}
 *SKU:* ${item.sku}
 *Precio:* ${precio}
 *Recomendado por:* ${item.tipo_recomendacion === 'morfologia' ? 'Forma de mi rostro (Morfología)' : 'Mi estación de color (Colorimetría)'}

¿Tienen disponibilidad y cuáles son los métodos de pago? Muchas gracias!`;

        const urlWa = `https://wa.me/${TELEFONO_WHATSAPP}?text=${encodeURIComponent(mensaje)}`;
        window.open(urlWa, '_blank');
    }

    // ============================================================
    //  6. Pedido de Toda la Lista por WhatsApp
    // ============================================================
    btnPedirTodosWhatsApp.addEventListener('click', () => {
        if (!listaIntereses || listaIntereses.length === 0) return;

        const nombreCliente = (usuario.nombre || 'Cliente').trim();
        let totalDinero = 0;
        let lineasProductos = '';

        listaIntereses.forEach((item, index) => {
            const p = item.producto || {};
            const precioStr = p.precio != null ? `$${Number(p.precio).toFixed(2)}` : 'A consultar';
            if (p.precio != null) totalDinero += Number(p.precio);
            lineasProductos += `\n${index + 1}. *${p.descripcion || item.sku}* (SKU: ${item.sku}) - ${precioStr}`;
        });

        const totalTexto = totalDinero > 0 ? `\n\n *Total estimado:* $${totalDinero.toFixed(2)}` : '';

        const mensaje = 
`Hola LUMIII! 
Mi nombre es *${nombreCliente}*. Me realicé el diagnóstico en su plataforma y guardé mi lista de productos favoritos recomendados:
${lineasProductos}${totalTexto}

¿Me podrían brindar información sobre disponibilidad, entregas y métodos de pago para concretar la compra? ¡Gracias!`;

        const urlWa = `https://wa.me/${TELEFONO_WHATSAPP}?text=${encodeURIComponent(mensaje)}`;
        window.open(urlWa, '_blank');
    });

    // ============================================================
    //  7. Eliminar Favorito
    // ============================================================
    async function eliminarFavorito(idInteres, elementoTarjeta) {
        if (!confirm('¿Quieres quitar este producto de tus favoritos?')) return;

        try {
            const resp = await LumiiiAuth.fetch(`${URL_SERVIDOR}/api/interes/${idInteres}`, {
                method: 'DELETE',
            });
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                throw new Error(err.detail || `Error ${resp.status}`);
            }

            // Eliminar del array local
            listaIntereses = listaIntereses.filter((i) => i.id !== idInteres);
            renderizarVista();
        } catch (e) {
            alert('No se pudo eliminar: ' + e.message);
        }
    }

    // Carga inicial
    cargarFavoritos();
});

document.addEventListener('DOMContentLoaded', () => {
    const inputFoto = document.getElementById('inputFoto');
    const btnAnalizar = document.getElementById('btnAnalizar');
    const vistaPrevia = document.getElementById('vistaPrevia');
    const textoError = document.getElementById('textoError');

    const panelesResultado = document.getElementById('panelesResultado');

    const textoMorfologia = document.getElementById('textoMorfologia');
    const textoAsesoriaMorfologia = document.getElementById('textoAsesoriaMorfologia');
    const galeriaMorfologia = document.getElementById('galeriaMorfologia');

    const textoEstacion = document.getElementById('textoEstacion');
    const textoAsesoriaEstacion = document.getElementById('textoAsesoriaEstacion');
    const galeriaEstacion = document.getElementById('galeriaEstacion');

    const URL_SERVIDOR = (typeof LumiiiAuth !== 'undefined' && LumiiiAuth.URL_SERVIDOR !== undefined)
        ? LumiiiAuth.URL_SERVIDOR
        : ((window.location && window.location.protocol && window.location.protocol.startsWith('http')) ? '' : 'http://localhost:8080');

    // Mismos códigos que MAPA_ESTACION / MAPA_MORFOLOGIA en server.py,
    // usados aquí solo para pintar cada panel con su color real (ver styles.css).
    const CODIGO_POR_ESTACION = {
        'Invierno': 'CIN',
        'Verano': 'CVE',
        'Otoño': 'COT',
        'Primavera': 'CPR',
        'Indeterminado': 'INDETERMINADO',
    };
    const CODIGO_POR_MORFOLOGIA = {
        'Redondo': 'MRE',
        'Cuadrado': 'MCU',
        'Diamante': 'MDI',
        'Ovalado': 'MOV',
    };

    function aplicarColorResultado(panel, codigo) {
        if (!panel) return;
        [...panel.classList].forEach((clase) => {
            if (clase.startsWith('resultado-')) panel.classList.remove(clase);
        });
        if (codigo) panel.classList.add(`resultado-${codigo}`);
    }

    // Orden y nombre "bonito" con que se muestran las categorías dentro de cada panel.
    // Si mañana agregas una nueva prenda al catálogo, súmala aquí y ya sale sola.
    const CATEGORIAS_ORDENADAS = [
        { clave: 'lentes',   titulo: 'Lentes'    },
        { clave: 'bufandas', titulo: 'Bufandas'  },
        { clave: 'cintillo', titulo: 'Cintillos' },
        { clave: 'chaqueta', titulo: 'Chaquetas' },
        { clave: 'franelas', titulo: 'Franelas'  },
    ];

    function crearTarjetaModelo(modelo, tipoRecomendacion) {
        const tarjeta = document.createElement('div');
        tarjeta.className = 'tarjeta-modelo';

        const img = document.createElement('img');
        img.src = URL_SERVIDOR + modelo.imagen_url;
        img.alt = modelo.descripcion || modelo.sku;
        img.loading = 'lazy';

        const descripcion = document.createElement('p');
        descripcion.className = 'descripcion-modelo';
        descripcion.innerText = modelo.descripcion || modelo.sku;

        const btnInteres = document.createElement('button');
        btnInteres.type = 'button';
        btnInteres.className = 'boton-me-interesa';
        btnInteres.innerText = '♡ Me interesa';
        btnInteres.addEventListener('click', () => marcarInteres(modelo.sku, tipoRecomendacion, btnInteres));

        tarjeta.appendChild(img);
        tarjeta.appendChild(descripcion);
        tarjeta.appendChild(btnInteres);
        return tarjeta;
    }

    // Guarda el "Me interesa" en el servidor. Si no hay sesión, invita a
    // iniciar sesión en vez de fallar en silencio (sin usuario no hay a
    // quién asociar el interés).
    async function marcarInteres(sku, tipoRecomendacion, boton) {
        const usuario = await LumiiiAuth.usuarioActual();
        if (!usuario) {
            if (confirm('Inicia sesión para guardar tus favoritos. ¿Quieres ir a iniciar sesión?')) {
                window.location.href = 'login.html';
            }
            return;
        }

        boton.disabled = true;
        boton.innerText = 'Guardando...';
        try {
            const resp = await LumiiiAuth.fetch(`${URL_SERVIDOR}/api/interes`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sku, tipo_recomendacion: tipoRecomendacion }),
            });
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                throw new Error(err.detail || `HTTP ${resp.status}`);
            }
            boton.innerText = '❤ Guardado';
            boton.classList.add('guardado');
        } catch (e) {
            boton.disabled = false;
            boton.innerText = '♡ Me interesa';
            alert('No se pudo guardar: ' + e.message);
        }
    }

    function pintarSeccionesPorCategoria(contenedor, modelosPorCategoria, tipoRecomendacion) {
        contenedor.innerHTML = '';

        // Nada que mostrar -> mensaje único
        const hayAlgo = modelosPorCategoria
            && Object.values(modelosPorCategoria).some(lista => lista && lista.length > 0);
        if (!hayAlgo) {
            contenedor.innerHTML = '<p class="sin-modelos">Aún no hay modelos cargados para este resultado.</p>';
            return;
        }

        // Recorrer en el orden fijo. Categorías vacías se saltan.
        CATEGORIAS_ORDENADAS.forEach(({ clave, titulo }) => {
            const modelos = modelosPorCategoria[clave];
            if (!modelos || modelos.length === 0) return;

            const seccion = document.createElement('div');
            seccion.className = 'seccion-categoria';

            const encabezado = document.createElement('h3');
            encabezado.className = 'titulo-categoria';
            encabezado.innerText = titulo;
            seccion.appendChild(encabezado);

            const galeria = document.createElement('div');
            galeria.className = 'galeria-modelos';
            modelos.forEach(modelo => galeria.appendChild(crearTarjetaModelo(modelo, tipoRecomendacion)));

            seccion.appendChild(galeria);
            contenedor.appendChild(seccion);
        });
    }

    inputFoto.addEventListener('change', (evento) => {
        const archivo = evento.target.files[0];
        if (archivo) {
            vistaPrevia.src = URL.createObjectURL(archivo);
            vistaPrevia.style.display = 'block';
            panelesResultado.style.display = 'none';
            textoError.style.display = 'none';
        }
    });

    btnAnalizar.addEventListener('click', async () => {
        if (inputFoto.files.length === 0) {
            alert('Carga una imagen primero.');
            return;
        }

        const formData = new FormData();
        formData.append('imagen', inputFoto.files[0]);
        // Sin filtro: el servidor devuelve modelos de TODAS las categorías.
        // Si algún día quieres filtrar, manda formData.append('categoria', 'lentes').

        textoError.style.display = 'none';
        panelesResultado.style.display = 'grid';
        textoMorfologia.innerText = 'Procesando...';
        textoEstacion.innerText = 'Procesando...';
        textoAsesoriaMorfologia.innerText = '';
        textoAsesoriaEstacion.innerText = '';
        galeriaMorfologia.innerHTML = '';
        galeriaEstacion.innerHTML = '';

        try {
            // LumiiiAuth.fetch (definido en auth.js) manda el header X-Auth-Token
            // automáticamente si hay sesión activa. Con `fetch` normal el servidor
            // nunca se entera de quién eres y el historial opt-in nunca se guarda.
            const respuesta = await LumiiiAuth.fetch(`${URL_SERVIDOR}/api/analizar`, {
                method: 'POST',
                body: formData
            });

            const json = await respuesta.json();

            if (respuesta.ok && json.estatus === 'ok') {
                const panelMorfologia = textoMorfologia.closest('.panel-columna');
                const panelEstacion = textoEstacion.closest('.panel-columna');

                textoMorfologia.innerText = json.morfologia;
                aplicarColorResultado(panelMorfologia, CODIGO_POR_MORFOLOGIA[json.morfologia]);
                textoAsesoriaMorfologia.innerText = json.asesoria_morfologia || '';
                pintarSeccionesPorCategoria(galeriaMorfologia, json.modelos_morfologia, 'morfologia');

                textoEstacion.innerText = json.estacion;
                aplicarColorResultado(panelEstacion, CODIGO_POR_ESTACION[json.estacion]);
                textoAsesoriaEstacion.innerText = json.asesoria_estacion || '';
                pintarSeccionesPorCategoria(galeriaEstacion, json.modelos_colorimetria, 'colorimetria');
            } else {
                panelesResultado.style.display = 'none';
                textoError.innerText = 'Error: ' + (json.error || 'Desconocido');
                textoError.style.display = 'block';
            }
        } catch (error) {
            console.error('Error de red:', error);
            panelesResultado.style.display = 'none';
            textoError.innerText = 'No se pudo conectar con el servidor. Intenta nuevamente.';
            textoError.style.display = 'block';
        }
    });
});

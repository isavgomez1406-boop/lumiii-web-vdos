document.addEventListener('DOMContentLoaded', async () => {
    const URL_SERVIDOR = (typeof LumiiiAuth !== 'undefined' && LumiiiAuth.URL_SERVIDOR !== undefined)
        ? LumiiiAuth.URL_SERVIDOR
        : ((window.location && window.location.protocol && window.location.protocol.startsWith('http')) ? '' : 'http://localhost:8080');

    const textoCargando = document.getElementById('textoCargando');
    const textoErrorCatalogo = document.getElementById('textoErrorCatalogo');
    const vistaColorimetria = document.getElementById('vistaColorimetria');
    const vistaMorfologia = document.getElementById('vistaMorfologia');
    const vistaProductos = document.getElementById('vistaProductos');
    const pestanas = document.querySelectorAll('.pestana');

    // Mismo orden/nombres "bonitos" que usa script.js en la página de análisis
    const CATEGORIAS_ORDENADAS = [
        { clave: 'lentes',   titulo: 'Lentes'    },
        { clave: 'bufandas', titulo: 'Bufandas'  },
        { clave: 'cintillo', titulo: 'Cintillos' },
        { clave: 'chaqueta', titulo: 'Chaquetas' },
        { clave: 'franelas', titulo: 'Franelas'  },
    ];

    // Códigos de resultado agrupados por enfoque, con su nombre visible y orden
    const GRUPOS_COLORIMETRIA = [
        { codigo: 'CIN', titulo: 'Invierno' },
        { codigo: 'CVE', titulo: 'Verano' },
        { codigo: 'COT', titulo: 'Otoño' },
        { codigo: 'CPR', titulo: 'Primavera' },
    ];
    const GRUPOS_MORFOLOGIA = [
        { codigo: 'MRE', titulo: 'Redondo' },
        { codigo: 'MCU', titulo: 'Cuadrado' },
        { codigo: 'MDI', titulo: 'Diamante' },
        { codigo: 'MOV', titulo: 'Ovalado' },
    ];

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
                body: JSON.stringify({ sku, tipo_recomendacion: tipoRecomendacion || 'colorimetria' }),
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

    function crearTarjetaModelo(sku, info, tipoRecomendacion) {
        const tarjeta = document.createElement('div');
        tarjeta.className = 'tarjeta-modelo';

        const img = document.createElement('img');
        img.src = `${URL_SERVIDOR}/catalogo/${info.categoria}/${info.codigo}/${sku}.png`;
        img.alt = info.descripcion || sku;
        img.loading = 'lazy';
        img.onerror = () => { tarjeta.style.display = 'none'; };

        const descripcion = document.createElement('p');
        descripcion.className = 'descripcion-modelo';
        descripcion.innerText = info.descripcion || sku;

        const tipo = tipoRecomendacion || (info.enfoque === 'morfologia' ? 'morfologia' : 'colorimetria');
        const btnInteres = document.createElement('button');
        btnInteres.type = 'button';
        btnInteres.className = 'boton-me-interesa';
        btnInteres.innerText = '♡ Me interesa';
        btnInteres.addEventListener('click', () => marcarInteres(sku, tipo, btnInteres));

        tarjeta.appendChild(img);
        tarjeta.appendChild(descripcion);
        tarjeta.appendChild(btnInteres);
        return tarjeta;
    }

    function construirVista(contenedor, grupos, catalogoPorCodigo) {
        contenedor.innerHTML = '';

        grupos.forEach(({ codigo, titulo }) => {
            const seccionGrupo = document.createElement('div');
            seccionGrupo.className = `grupo-resultado resultado-${codigo}`;

            const tituloGrupo = document.createElement('h2');
            tituloGrupo.className = 'titulo-grupo';
            tituloGrupo.innerText = titulo;
            seccionGrupo.appendChild(tituloGrupo);

            const itemsDelCodigo = catalogoPorCodigo[codigo] || {};
            const categoriasConItems = CATEGORIAS_ORDENADAS.filter(
                ({ clave }) => itemsDelCodigo[clave] && itemsDelCodigo[clave].length > 0
            );

            if (categoriasConItems.length === 0) {
                const vacio = document.createElement('p');
                vacio.className = 'sin-modelos';
                vacio.innerText = 'Aún no hay modelos cargados para este grupo.';
                seccionGrupo.appendChild(vacio);
                contenedor.appendChild(seccionGrupo);
                return;
            }

            categoriasConItems.forEach(({ clave, titulo: tituloCategoria }) => {
                const seccionCategoria = document.createElement('div');
                seccionCategoria.className = 'seccion-categoria';

                const h3 = document.createElement('h3');
                h3.className = 'titulo-categoria';
                h3.innerText = tituloCategoria;
                seccionCategoria.appendChild(h3);

                const galeria = document.createElement('div');
                galeria.className = 'galeria-modelos';
                itemsDelCodigo[clave].forEach(({ sku, info }) => {
                    galeria.appendChild(crearTarjetaModelo(sku, info));
                });
                seccionCategoria.appendChild(galeria);

                seccionGrupo.appendChild(seccionCategoria);
            });

            contenedor.appendChild(seccionGrupo);
        });
    }

    function construirVistaProductos(contenedor, grupos, catalogoPorCategoria) {
        contenedor.innerHTML = '';

        grupos.forEach(({ clave, titulo }) => {
            const items = catalogoPorCategoria[clave] || [];

            const seccionGrupo = document.createElement('div');
            seccionGrupo.className = 'grupo-resultado';

            const tituloGrupo = document.createElement('h2');
            tituloGrupo.className = 'titulo-grupo';
            tituloGrupo.innerText = titulo;
            seccionGrupo.appendChild(tituloGrupo);

            if (items.length === 0) {
                const vacio = document.createElement('p');
                vacio.className = 'sin-modelos';
                vacio.innerText = 'Aún no hay modelos cargados para esta categoría.';
                seccionGrupo.appendChild(vacio);
                contenedor.appendChild(seccionGrupo);
                return;
            }

            const galeria = document.createElement('div');
            galeria.className = 'galeria-modelos';
            items.forEach(({ sku, info }) => {
                galeria.appendChild(crearTarjetaModelo(sku, info));
            });
            seccionGrupo.appendChild(galeria);

            contenedor.appendChild(seccionGrupo);
        });
    }

    // Cambiar de pestaña (Colorimetría / Morfología / Productos)
    const VISTAS = {
        colorimetria: vistaColorimetria,
        morfologia: vistaMorfologia,
        productos: vistaProductos,
    };
    pestanas.forEach((boton) => {
        boton.addEventListener('click', () => {
            pestanas.forEach((b) => b.classList.remove('activa'));
            boton.classList.add('activa');

            Object.entries(VISTAS).forEach(([clave, vista]) => {
                vista.style.display = clave === boton.dataset.tab ? 'block' : 'none';
            });
        });
    });

    try {
        // CAMBIO PASO 2: leemos de /api/catalogo (BD) en vez del JSON estático,
        // así el catálogo mostrado refleja siempre lo que el vendedor edita.
        const respuesta = await fetch(`${URL_SERVIDOR}/api/catalogo`);
        if (!respuesta.ok) throw new Error('No se pudo cargar /api/catalogo');
        const catalogo = await respuesta.json();

        // Reorganizar: { codigo: { categoria: [ {sku, info}, ... ] } }
        const catalogoPorCodigo = {};
        // Reorganizar: { categoria: [ {sku, info}, ... ] }  (para la pestaña "Productos")
        const catalogoPorCategoria = {};
        Object.entries(catalogo).forEach(([sku, info]) => {
            if (!catalogoPorCodigo[info.codigo]) catalogoPorCodigo[info.codigo] = {};
            if (!catalogoPorCodigo[info.codigo][info.categoria]) catalogoPorCodigo[info.codigo][info.categoria] = [];
            catalogoPorCodigo[info.codigo][info.categoria].push({ sku, info });

            if (!catalogoPorCategoria[info.categoria]) catalogoPorCategoria[info.categoria] = [];
            catalogoPorCategoria[info.categoria].push({ sku, info });
        });

        construirVista(vistaColorimetria, GRUPOS_COLORIMETRIA, catalogoPorCodigo);
        construirVista(vistaMorfologia, GRUPOS_MORFOLOGIA, catalogoPorCodigo);
        construirVistaProductos(vistaProductos, CATEGORIAS_ORDENADAS, catalogoPorCategoria);

        textoCargando.style.display = 'none';
    } catch (error) {
        console.error('Error cargando el catálogo:', error);
        textoCargando.style.display = 'none';
        textoErrorCatalogo.innerText = 'No se pudo cargar el catálogo. Intenta nuevamente.';
        textoErrorCatalogo.style.display = 'block';
    }
});

// =============================================================================
// app.js — Mapa de eventos de Valledupar
// Todo corre en el navegador, sin backend: lee events.json y vias_y_rutas.json
// (archivos estáticos que actualiza el pipeline de Python / GitHub Actions).
// =============================================================================

const CENTRO_VALLEDUPAR = [10.4631, -73.2532];
const ZOOM_INICIAL = 14;

let mapa, capaEventos, eventosTodos = [], categoriaActiva = 'todas', textoBusqueda = '';

// -----------------------------------------------------------------------------
// Utilidades de fecha/hora
// -----------------------------------------------------------------------------
function hoyISO() {
  const d = new Date();
  return d.toISOString().slice(0, 10);
}

function actualizarReloj() {
  const el = document.getElementById('reloj');
  if (!el) return;
  const ahora = new Date();
  const opciones = { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' };
  el.textContent = ahora.toLocaleDateString('es-CO', opciones);
}

function esEventoDeHoy(evento) {
  return evento.fecha_iso === hoyISO();
}

// -----------------------------------------------------------------------------
// Inicialización del mapa
// -----------------------------------------------------------------------------
function iniciarMapa() {
  mapa = L.map('mapa', {
    zoomControl: false,
    attributionControl: true,
  }).setView(CENTRO_VALLEDUPAR, ZOOM_INICIAL);

  L.control.zoom({ position: 'bottomright' }).addTo(mapa);

  // Tiles claros y minimalistas (CartoDB Positron, gratuito con atribución)
  L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 19,
  }).addTo(mapa);

  capaEventos = L.layerGroup().addTo(mapa);
}

// -----------------------------------------------------------------------------
// Marcadores de eventos
// -----------------------------------------------------------------------------
function iconoEvento(evento, enCurso) {
  const html = `<div class="marcador-evento ${enCurso ? 'en-curso' : ''}" style="--marca-color:${evento.color}">
                  <span>${evento.icono || '📍'}</span>
                </div>`;
  return L.divIcon({ html, className: '', iconSize: [38, 38], iconAnchor: [19, 34], popupAnchor: [0, -30] });
}

function construirPopup(evento, enCurso) {
  const badge = enCurso ? `<div class="popup-evento__badge-ahora">En curso ahora</div>` : '';
  return `
    <div class="popup-evento" style="--marca-color:${evento.color}">
      <div class="popup-evento__cabecera">
        <div class="popup-evento__icono">${evento.icono || '📍'}</div>
        <div class="popup-evento__entidad">${evento.institucion_nombre}</div>
      </div>
      <div class="popup-evento__titulo">${evento.titulo}</div>
      ${badge}
      <div class="popup-evento__datos">
        ${evento.hora_texto ? `<div class="popup-evento__dato">🕒 <strong>${evento.hora_texto}</strong></div>` : ''}
        ${evento.fecha_texto ? `<div class="popup-evento__dato">📅 ${evento.fecha_texto}</div>` : `<div class="popup-evento__dato">📅 ${evento.fecha_iso}</div>`}
        ${evento.direccion_texto ? `<div class="popup-evento__dato">📍 ${evento.direccion_texto}</div>` : ''}
      </div>
      <a class="popup-evento__enlace" href="${evento.url_publicacion}" target="_blank" rel="noopener">Ver publicación original</a>
    </div>
  `;
}

function pintarEventos() {
  capaEventos.clearLayers();
  const visibles = filtrarEventos();

  visibles.forEach(evento => {
    if (typeof evento.lat !== 'number' || typeof evento.lon !== 'number') return;
    const enCurso = esEventoDeHoy(evento);
    const marcador = L.marker([evento.lat, evento.lon], { icon: iconoEvento(evento, enCurso) });
    marcador.bindPopup(construirPopup(evento, enCurso));
    marcador.addTo(capaEventos);
  });

  actualizarEstado(visibles.length);
  pintarListaEventos(visibles);
}

function filtrarEventos() {
  return eventosTodos.filter(ev => {
    if (categoriaActiva !== 'todas' && ev.categoria !== categoriaActiva) return false;
    if (textoBusqueda) {
      const q = textoBusqueda.toLowerCase();
      const enTexto = `${ev.titulo} ${ev.institucion_nombre} ${ev.direccion_texto || ''}`.toLowerCase();
      if (!enTexto.includes(q)) return false;
    }
    return true;
  });
}

function actualizarEstado(cantidad) {
  const texto = document.getElementById('mapa-estado-texto');
  if (!texto) return;
  texto.textContent = cantidad === 1 ? '1 evento en el mapa' : `${cantidad} eventos en el mapa`;
}

// -----------------------------------------------------------------------------
// Panel lateral: lista de eventos
// -----------------------------------------------------------------------------
function pintarListaEventos(eventos) {
  const contenedor = document.getElementById('lista-eventos');
  if (!contenedor) return;

  const ordenados = [...eventos].sort((a, b) => (a.fecha_iso || '').localeCompare(b.fecha_iso || ''));

  if (ordenados.length === 0) {
    contenedor.innerHTML = `<div class="lista-vacia">No hay eventos que coincidan con este filtro.</div>`;
    return;
  }

  contenedor.innerHTML = ordenados.map(ev => `
    <div class="tarjeta-evento" style="--marca-color:${ev.color}" data-lat="${ev.lat}" data-lon="${ev.lon}">
      <div class="tarjeta-evento__icono">${ev.icono || '📍'}</div>
      <div>
        <p class="tarjeta-evento__titulo">${ev.titulo}</p>
        <div class="tarjeta-evento__meta">${ev.fecha_texto || ev.fecha_iso}${ev.hora_texto ? ' · ' + ev.hora_texto : ''}</div>
        <div class="tarjeta-evento__entidad">${ev.institucion_nombre}</div>
      </div>
    </div>
  `).join('');

  contenedor.querySelectorAll('.tarjeta-evento').forEach(el => {
    el.addEventListener('click', () => {
      const lat = parseFloat(el.dataset.lat), lon = parseFloat(el.dataset.lon);
      if (!isNaN(lat) && !isNaN(lon)) {
        mapa.flyTo([lat, lon], 16, { duration: 0.6 });
        cerrarPanelLista();
      }
    });
  });
}

function abrirPanelLista() {
  document.getElementById('panel-lista').classList.add('abierto');
  document.getElementById('btn-lista').setAttribute('aria-expanded', 'true');
}
function cerrarPanelLista() {
  document.getElementById('panel-lista').classList.remove('abierto');
  document.getElementById('btn-lista').setAttribute('aria-expanded', 'false');
}

// -----------------------------------------------------------------------------
// Filtros (teclado de acordeón)
// -----------------------------------------------------------------------------
function inicializarFiltros() {
  document.querySelectorAll('.tecla').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tecla').forEach(b => b.classList.remove('is-active'));
      btn.classList.add('is-active');
      categoriaActiva = btn.dataset.categoria;
      pintarEventos();
    });
  });
}

// -----------------------------------------------------------------------------
// Carga de datos (con manejo de errores — punto 6 del requerimiento)
// -----------------------------------------------------------------------------
async function cargarEventos() {
  try {
    const resp = await fetch('events.json', { cache: 'no-store' });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    eventosTodos = Array.isArray(data.eventos) ? data.eventos : [];
    pintarEventos();
  } catch (err) {
    console.error('No se pudo cargar events.json:', err);
    document.getElementById('mapa-estado-texto').textContent =
      'No se pudieron cargar los eventos. Intenta recargar la página.';
  }
}

async function cargarViasYRutas() {
  try {
    const resp = await fetch('../config/vias_y_rutas.json', { cache: 'no-store' });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return await resp.json();
  } catch (err) {
    console.warn('No se pudieron cargar vías/rutas (las animaciones se omiten):', err);
    return null;
  }
}

// -----------------------------------------------------------------------------
// Animaciones: carros en vías, buses SIVA, avión, buses de terminal
// -----------------------------------------------------------------------------
function crearVehiculoAnimado(puntos, emoji, duracionMs, tamano = 18) {
  if (!puntos || puntos.length < 2) return;

  const icono = L.divIcon({
    html: `<div class="marcador-vehiculo" style="font-size:${tamano}px">${emoji}</div>`,
    className: '', iconSize: [tamano + 6, tamano + 6], iconAnchor: [(tamano + 6) / 2, (tamano + 6) / 2],
  });
  const marcador = L.marker(puntos[0], { icon: icono, interactive: false }).addTo(mapa);

  const segmentos = puntos.length - 1;
  let inicio = null;

  function paso(timestamp) {
    if (!inicio) inicio = timestamp;
    const progreso = ((timestamp - inicio) % duracionMs) / duracionMs; // 0..1 en loop
    const posGlobal = progreso * segmentos;
    const i = Math.min(Math.floor(posGlobal), segmentos - 1);
    const t = posGlobal - i;

    const [lat1, lon1] = puntos[i];
    const [lat2, lon2] = puntos[i + 1];
    const lat = lat1 + (lat2 - lat1) * t;
    const lon = lon1 + (lon2 - lon1) * t;
    marcador.setLatLng([lat, lon]);

    requestAnimationFrame(paso);
  }
  requestAnimationFrame(paso);
}

function dibujarViaPrincipal(via) {
  L.polyline(via.puntos, {
    color: '#C99A2E', weight: 3, opacity: 0.35, dashArray: '1,8', lineCap: 'round',
  }).addTo(mapa);
}

function dibujarRutaSiva(ruta) {
  L.polyline(ruta.puntos, {
    color: ruta.color || '#6C5B9E', weight: 2.5, opacity: 0.4,
  }).addTo(mapa);
  // Un bus recorriendo la ruta en loop continuo; duración variable para que no
  // todos los buses se muevan sincronizados (se ve más orgánico).
  const duracion = 26000 + Math.random() * 10000;
  crearVehiculoAnimado(ruta.puntos, '🚍', duracion, 17);
}

function iniciarAnimacionesVehiculos(datos) {
  if (!datos) return;

  (datos.vias_principales || []).forEach(dibujarViaPrincipal);

  // Un par de carros circulando por las avenidas principales (decorativo)
  (datos.vias_principales || []).slice(0, 2).forEach(via => {
    crearVehiculoAnimado(via.puntos, '🚗', 18000 + Math.random() * 6000, 15);
  });

  (datos.rutas_siva || []).forEach(dibujarRutaSiva);
}

function iniciarAvionAeropuerto() {
  // Trayecto corto de aproximación/despegue sobre el aeropuerto, puramente
  // ambiental (no representa vuelos reales en tiempo real).
  const pista = [
    [10.4260, -73.2610],
    [10.4300, -73.2550],
    [10.4333, -73.2497],
    [10.4370, -73.2440],
    [10.4410, -73.2380],
  ];
  crearVehiculoAnimado(pista, '✈️', 22000, 20);
}

// -----------------------------------------------------------------------------
// Reloj "en vivo" para saber qué eventos están sucediendo ahora mismo
// -----------------------------------------------------------------------------
function iniciarRelojEnVivo() {
  actualizarReloj();
  setInterval(actualizarReloj, 30000);
  // Repinta cada 5 min para refrescar el estado "en curso ahora"
  setInterval(pintarEventos, 5 * 60 * 1000);
}

// -----------------------------------------------------------------------------
// Actualización automática: vuelve a pedir events.json periódicamente sin
// recargar la página (punto 5 del requerimiento: reflejar altas/bajas).
// -----------------------------------------------------------------------------
function iniciarActualizacionAutomatica() {
  const INTERVALO_MS = 10 * 60 * 1000; // 10 minutos
  setInterval(cargarEventos, INTERVALO_MS);
}

// -----------------------------------------------------------------------------
// Modal QR
// -----------------------------------------------------------------------------
function inicializarModalQR() {
  const fondo = document.getElementById('modal-qr-fondo');
  const contenedor = document.getElementById('qr-contenedor');
  let canvasQR = null;

  document.getElementById('btn-qr').addEventListener('click', () => {
    fondo.classList.add('abierto');
    if (!canvasQR) {
      const urlActual = window.location.href.split('?')[0];
      QRCode.toCanvas(urlActual, { width: 260, margin: 1, color: { dark: '#0F2E33', light: '#FFFFFF' } },
        (err, canvas) => {
          if (err) { contenedor.textContent = 'No se pudo generar el QR.'; return; }
          canvasQR = canvas;
          contenedor.appendChild(canvas);
        });
    }
  });

  document.getElementById('cerrar-qr').addEventListener('click', () => fondo.classList.remove('abierto'));
  fondo.addEventListener('click', (e) => { if (e.target === fondo) fondo.classList.remove('abierto'); });

  document.getElementById('descargar-qr').addEventListener('click', () => {
    if (!canvasQR) return;
    // Se genera una versión de alta resolución aparte, pensada para imprimir.
    QRCode.toDataURL(window.location.href.split('?')[0], { width: 1200, margin: 2 }, (err, url) => {
      if (err) return;
      const a = document.createElement('a');
      a.href = url;
      a.download = 'mapa-eventos-valledupar-qr.png';
      a.click();
    });
  });
}

// -----------------------------------------------------------------------------
// Panel lista + búsqueda
// -----------------------------------------------------------------------------
function inicializarPanelLista() {
  document.getElementById('btn-lista').addEventListener('click', abrirPanelLista);
  document.getElementById('cerrar-lista').addEventListener('click', cerrarPanelLista);
  document.getElementById('buscador').addEventListener('input', (e) => {
    textoBusqueda = e.target.value.trim();
    pintarEventos();
  });
}

// -----------------------------------------------------------------------------
// Arranque
// -----------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', async () => {
  iniciarMapa();
  inicializarFiltros();
  inicializarPanelLista();
  inicializarModalQR();
  iniciarRelojEnVivo();

  await cargarEventos();
  iniciarActualizacionAutomatica();

  const datosVias = await cargarViasYRutas();
  iniciarAnimacionesVehiculos(datosVias);
  iniciarAvionAeropuerto();
});

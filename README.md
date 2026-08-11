# Valledupar en su pulso — Mapa de eventos institucionales y comerciales

Mapa interactivo, gratuito y de actualización automática, que reúne eventos
publicados en Instagram por instituciones y empresas de Valledupar (Cesar,
Colombia): alcaldía, gobernación, cámara de comercio, universidades, SENA,
transporte, servicios públicos, etc.

**Ver el mapa:** una vez desplegado, `https://TU-USUARIO.github.io/valledupar-eventos/`

---

## 1. Qué es esto y qué NO es

Esto es un sistema **100% gratuito**, hecho con herramientas gratuitas:

| Pieza                     | Herramienta                          | Costo |
|---------------------------|---------------------------------------|-------|
| Mapa                       | Leaflet.js + tiles CartoDB Positron   | Gratis |
| Geocodificación            | Nominatim (OpenStreetMap)             | Gratis |
| Hosting                    | GitHub Pages                          | Gratis |
| Automatización periódica   | GitHub Actions (repos públicos)       | Gratis |
| Extracción de Instagram    | `instaloader` (no oficial)            | Gratis, pero **frágil** |
| QR                         | librería `qrcode` (Python) / `qrcode.js` (navegador) | Gratis |

### ⚠️ Advertencia honesta sobre el scraping de Instagram

Instagram **no tiene una API pública gratuita** para leer cuentas que no
administras tú. Este proyecto usa `instaloader` para leer perfiles
**públicos** sin iniciar sesión, tal como pediste. Eso significa:

- Puede dejar de funcionar en cualquier momento si Meta cambia su
  plataforma — no es un bug del código, es una limitación estructural.
- Un uso muy frecuente o agresivo puede resultar en bloqueos temporales
  de IP por parte de Instagram.
- Técnicamente puede estar en tensión con los Términos de Servicio de
  Meta, que prohíben el scraping automatizado.

El pipeline está diseñado para **degradar con elegancia**: si una cuenta
falla, se usa la última copia buena en caché y las demás cuentas no se ven
afectadas (ver `scraper/instagram_scraper.py`). Aun así, revisa
periódicamente los logs de GitHub Actions para detectar cuentas que dejaron
de responder.

**Recomendación a futuro:** si el scraping se vuelve inestable, la
alternativa más robusta es un formulario simple (Google Forms) donde
alguien pegue el link del post y el sistema haga el resto (extracción +
geocodificación), quitando la dependencia del scraping no oficial.

---

## 2. Estructura del proyecto

```
valledupar-eventos/
├── config/
│   ├── institutions.json     # Lista de cuentas a monitorear (AQUÍ agregas nuevas)
│   └── vias_y_rutas.json     # Coordenadas de vías y rutas SIVA para animaciones
├── scraper/
│   ├── instagram_scraper.py  # Descarga posts públicos, con caché y reintentos
│   ├── event_extractor.py    # Detecta eventos por palabra clave + extrae dirección/fecha/hora
│   ├── geocoder.py           # Dirección de texto -> lat/lon (Nominatim)
│   └── pipeline.py           # Orquesta todo y escribe docs/events.json
├── docs/                      # Esto es lo que se publica en GitHub Pages
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   └── events.json           # Datos que consume el mapa (lo genera el pipeline)
├── scripts/
│   └── generate_qr.py        # Genera el QR en alta resolución para imprimir
├── cache/                     # Caché local del scraper y geocodificador
├── .github/workflows/
│   └── update-events.yml     # Automatización gratuita (GitHub Actions)
└── requirements.txt
```

---

## 3. Puesta en marcha (paso a paso)

### 3.1. Sube el proyecto a GitHub

1. Crea un repositorio **público** en GitHub llamado, por ejemplo,
   `valledupar-eventos`.
2. Sube todo el contenido de esta carpeta.
3. Ve a **Settings → Pages** y en "Build and deployment" selecciona
   **GitHub Actions** como fuente (no "Deploy from branch").

### 3.2. Verifica las cuentas de Instagram

Abre `config/institutions.json`. Los campos con `"verificado": false`
corresponden a cuentas que no pude confirmar al 100% por ambigüedad
(varias cuentas activas con nombres parecidos) — revísalas y corrige el
`"instagram"` si hace falta antes de poner esto en producción.

### 3.3. Corre el pipeline manualmente la primera vez (opcional, recomendado)

```bash
pip install -r requirements.txt
cd scraper
python pipeline.py
```

Esto genera `docs/events.json` con eventos reales. Revisa los logs: verás
exactamente qué cuentas fallaron y por qué.

### 3.4. Activa la automatización

El workflow `.github/workflows/update-events.yml` ya está configurado para:

- Correr cada 6 horas automáticamente.
- Correr manualmente desde la pestaña **Actions → Actualizar eventos y
  publicar mapa → Run workflow**.
- Publicar el resultado en GitHub Pages.
- Eliminar del mapa los eventos cuya fecha ya pasó (punto 5 del
  requerimiento) en cada corrida.

### 3.5. Genera el QR para imprimir

Una vez que sepas la URL final de GitHub Pages:

```bash
python scripts/generate_qr.py https://tu-usuario.github.io/valledupar-eventos/
```

Esto deja un PNG en alta resolución y un SVG vectorial en `docs/assets/`,
listos para imprimir en volantes o carteles. También puedes generar el QR
directamente desde el botón "QR" en la esquina superior del mapa.

---

## 4. Cómo agregar una nueva institución o dirección

Abre `config/institutions.json` y agrega un objeto al arreglo:

```json
{ "id": "nueva_entidad", "nombre": "Nombre visible", "instagram": "usuario_ig",
  "categoria": "institucional", "icono": "🏛️", "color": "#2C6E8C", "verificado": true }
```

Categorías válidas: `institucional`, `comercio`, `educacion`, `transporte`,
`seguridad`, `servicios_publicos`, `justicia`, `cultura_mercado`. Si agregas
una categoría nueva, añade también su botón-tecla correspondiente en
`docs/index.html` (sección `<nav class="acordeon">`) y su color en
`docs/style.css`.

No hace falta tocar ningún otro archivo: el scraper, el extractor y el mapa
leen automáticamente esta lista.

---

## 5. Cómo funciona la detección de eventos (resumen técnico)

1. **Scraping** (`instagram_scraper.py`): trae los últimos ~12 posts
   públicos de cada cuenta, de forma aislada por cuenta (un fallo no
   afecta a las demás) y con caché de respaldo.
2. **Extracción** (`event_extractor.py`): busca sinónimos de "evento"
   (reunión, conferencia, taller, seminario, foro, capacitación, jornada,
   feria, convocatoria, inauguración, lanzamiento, etc.), y si encuentra
   coincidencia, extrae:
   - Dirección (nomenclatura urbana: Calle/Carrera/Avenida + números, o
     lugares conocidos de Valledupar como el Parque de la Leyenda
     Vallenata).
   - Fecha (texto tipo "10 de agosto" o "10/08"; si no hay fecha
     explícita, se asume el día de publicación).
   - Hora.
3. **Geocodificación** (`geocoder.py`): convierte la dirección de texto en
   coordenadas usando Nominatim, con caché para no repetir consultas.
   Si no se puede geocodificar, el evento **se descarta del mapa** (nunca
   se inventan coordenadas).
4. **Fusión** (`pipeline.py`): combina eventos nuevos con los existentes,
   evita duplicados (ID estable por institución + post) y elimina los
   vencidos.

---

## 6. Manejo de errores (punto 6 del requerimiento)

- Cada cuenta de Instagram se procesa de forma aislada; un fallo no tumba
  las demás.
- Reintentos con backoff exponencial ante fallos de red.
- Caché local que sirve de respaldo si Instagram bloquea una petición.
- Si Nominatim falla, el evento se descarta (no se inventan coordenadas).
- Si el pipeline entero falla de forma inesperada, se conserva el
  `events.json` anterior en vez de dejar el mapa vacío.
- El frontend (`app.js`) muestra un mensaje claro si `events.json` no
  carga, en vez de fallar en silencio.

---

## 7. Sobre las animaciones (carros, buses, avión)

Son **decorativas**, no representan posiciones reales en tiempo real (no
existe una fuente gratuita de datos GPS en vivo de buses o taxis en
Valledupar). Recorren las coordenadas definidas en
`config/vias_y_rutas.json`, que puedes ajustar o afinar trazando tu propia
ruta en [geojson.io](https://geojson.io) y copiando los pares `[lat, lon]`.

---

## 8. Python vs JavaScript/Apps Script — por qué esta combinación

- **Python** para el backend (scraping, extracción de texto, geocodificación):
  más robusto para procesamiento de texto/regex y manejo de errores que
  Apps Script, y corre gratis en GitHub Actions sin depender de la cuota
  de ejecución de Google Apps Script.
- **JavaScript (vanilla) + Leaflet** para el frontend: no requiere
  build/compilación, se sirve directo como sitio estático en GitHub Pages,
  y Leaflet es la librería de mapas de código abierto más usada para este
  caso de uso (mucho más ligera que Google Maps/MyMaps, sin límites de
  cuota ni necesidad de API key).

# -*- coding: utf-8 -*-
"""
pipeline.py
-----------
Orquesta todo el proceso y escribe docs/events.json, que es el único
archivo que consume el mapa (docs/app.js).

Flujo:
  1. Cargar instituciones desde config/institutions.json
  2. Descargar publicaciones recientes (instagram_scraper) — aislado por cuenta
  3. Detectar cuáles son eventos y extraer dirección/fecha/hora (event_extractor)
  4. Geocodificar direcciones nuevas (geocoder) — con caché
  5. Fusionar con el events.json existente:
       - eventos nuevos se agregan
       - eventos cuya fecha ya pasó se eliminan (punto 5 del requerimiento)
       - eventos ya existentes no se duplican (dedup por id estable)
  6. Escribir docs/events.json + un log de ejecución para depurar fallos

Este script está pensado para correr desde GitHub Actions con cron
(ver .github/workflows/update-events.yml) — completamente gratuito.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime
from pathlib import Path

from event_extractor import analizar_publicacion
from geocoder import geocodificar
from instagram_scraper import obtener_todas

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pipeline")

RAIZ = Path(__file__).resolve().parent.parent
CONFIG_PATH = RAIZ / "config" / "institutions.json"
EVENTS_PATH = RAIZ / "docs" / "events.json"


def _id_estable(institucion_id: str, shortcode: str) -> str:
    """ID determinístico para poder deduplicar entre corridas sin guardar estado extra."""
    return hashlib.sha1(f"{institucion_id}:{shortcode}".encode()).hexdigest()[:16]


def cargar_instituciones() -> list[dict]:
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return data["instituciones"]


def cargar_eventos_existentes() -> dict[str, dict]:
    if not EVENTS_PATH.exists():
        return {}
    try:
        data = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
        return {e["id"]: e for e in data.get("eventos", [])}
    except Exception as e:
        logger.warning("No se pudo leer events.json existente (%s); se parte de cero.", e)
        return {}


def evento_vigente(evento: dict, hoy: date) -> bool:
    """Punto 5 del requerimiento: eliminar eventos cuya fecha ya pasó."""
    fecha_iso = evento.get("fecha_iso")
    if not fecha_iso:
        return True  # si no hay fecha clara, se conserva y se revisa manualmente
    try:
        return date.fromisoformat(fecha_iso) >= hoy
    except ValueError:
        return True


def construir_eventos_nuevos(instituciones: list[dict]) -> list[dict]:
    publicaciones_por_institucion = obtener_todas(instituciones)
    mapa_instituciones = {i["id"]: i for i in instituciones}

    nuevos = []
    for institucion_id, publicaciones in publicaciones_por_institucion.items():
        inst = mapa_instituciones[institucion_id]
        for pub in publicaciones:
            analisis = analizar_publicacion(pub.texto, pub.fecha_publicacion)
            if not analisis.es_evento:
                continue

            lat = lon = None
            if analisis.direccion_texto:
                coords = geocodificar(analisis.direccion_texto)
                if coords:
                    lat, lon = coords
            if lat is None and inst.get("lat_fallback"):
                # útil para instituciones como el aeropuerto/terminal, cuya
                # ubicación es fija y conocida aunque el post no dé dirección
                lat, lon = inst["lat_fallback"], inst["lon_fallback"]

            if lat is None:
                logger.info(
                    "Evento detectado sin coordenadas, se omite del mapa: %s (%s)",
                    analisis.titulo, pub.url,
                )
                continue

            nuevos.append({
                "id": _id_estable(institucion_id, pub.shortcode),
                "titulo": analisis.titulo,
                "institucion_id": institucion_id,
                "institucion_nombre": inst["nombre"],
                "categoria": inst["categoria"],
                "icono": inst["icono"],
                "color": inst["color"],
                "direccion_texto": analisis.direccion_texto,
                "fecha_texto": analisis.fecha_texto,
                "fecha_iso": analisis.fecha_iso,
                "hora_texto": analisis.hora_texto,
                "lat": lat,
                "lon": lon,
                "url_publicacion": pub.url,
                "fecha_extraccion": datetime.utcnow().isoformat(),
            })

    return nuevos


def ejecutar() -> None:
    logger.info("=== Iniciando actualización de eventos ===")
    instituciones = cargar_instituciones()
    existentes = cargar_eventos_existentes()
    hoy = date.today()

    # 1) Descartar vencidos (punto 5)
    vigentes = {k: v for k, v in existentes.items() if evento_vigente(v, hoy)}
    eliminados = len(existentes) - len(vigentes)

    # 2) Traer y fusionar nuevos (dedup automático por id estable)
    try:
        nuevos = construir_eventos_nuevos(instituciones)
    except Exception as e:
        # Red de seguridad total: si algo inesperado revienta el pipeline,
        # se conserva el events.json anterior en vez de dejar el mapa vacío.
        logger.error("Fallo crítico en la construcción de eventos: %s. Se conserva el archivo anterior.", e)
        nuevos = []

    agregados = 0
    for ev in nuevos:
        if ev["id"] not in vigentes:
            agregados += 1
        vigentes[ev["id"]] = ev  # también refresca datos si cambió el post

    salida = {
        "generado_en": datetime.utcnow().isoformat() + "Z",
        "total_eventos": len(vigentes),
        "eventos": sorted(vigentes.values(), key=lambda e: (e.get("fecha_iso") or "9999")),
    }

    EVENTS_PATH.parent.mkdir(exist_ok=True)
    EVENTS_PATH.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(
        "Listo: %d eventos vigentes (+%d nuevos, -%d vencidos eliminados). Escrito en %s",
        len(vigentes), agregados, eliminados, EVENTS_PATH,
    )


if __name__ == "__main__":
    ejecutar()

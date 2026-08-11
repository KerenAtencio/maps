# -*- coding: utf-8 -*-
"""
geocoder.py
-----------
Convierte una dirección de texto en (latitud, longitud) usando Nominatim
(OpenStreetMap), que es gratuito y no requiere API key.

Reglas de buen ciudadano con Nominatim (su política de uso lo exige):
  - Máximo 1 petición por segundo.
  - User-Agent identificable con datos de contacto.
  - Cachear agresivamente para no repetir la misma consulta.

Si Nominatim falla o no encuentra nada, se devuelve None: el evento se
descarta del mapa (nunca se inventan coordenadas). Ver pipeline.py para
cómo se maneja ese caso.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger("geocoder")

CACHE_PATH = Path(__file__).resolve().parent.parent / "cache" / "geocoding_cache.json"
CACHE_PATH.parent.mkdir(exist_ok=True)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Cambia el email de contacto por uno real antes de desplegar en producción;
# Nominatim puede bloquear peticiones sin User-Agent identificable.
USER_AGENT = "mapa-eventos-valledupar/1.0 (contacto: tu-email@ejemplo.com)"

CIUDAD_SESGO = "Valledupar, Cesar, Colombia"
ESPERA_ENTRE_PETICIONES = 1.1  # segundos; respeta el límite de 1 req/seg de Nominatim
MAX_REINTENTOS = 3


def _cargar_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Caché de geocodificación corrupta, se reinicia.")
    return {}


def _guardar_cache(cache: dict) -> None:
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


_cache = _cargar_cache()


def geocodificar(direccion: str) -> Optional[tuple[float, float]]:
    """
    Devuelve (lat, lon) o None si no se pudo geocodificar.
    """
    if not direccion:
        return None

    clave_cache = direccion.strip().lower()
    if clave_cache in _cache:
        valor = _cache[clave_cache]
        return tuple(valor) if valor else None

    consulta = direccion if "valledupar" in direccion.lower() else f"{direccion}, {CIUDAD_SESGO}"

    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            resp = requests.get(
                NOMINATIM_URL,
                params={
                    "q": consulta,
                    "format": "json",
                    "limit": 1,
                    "countrycodes": "co",
                },
                headers={"User-Agent": USER_AGENT},
                timeout=10,
            )
            resp.raise_for_status()
            resultados = resp.json()
            time.sleep(ESPERA_ENTRE_PETICIONES)

            if not resultados:
                logger.info("Sin resultados de geocodificación para: %s", consulta)
                _cache[clave_cache] = None
                _guardar_cache(_cache)
                return None

            lat = float(resultados[0]["lat"])
            lon = float(resultados[0]["lon"])
            _cache[clave_cache] = [lat, lon]
            _guardar_cache(_cache)
            return (lat, lon)

        except requests.RequestException as e:
            logger.warning(
                "Intento %d/%d de geocodificación falló para '%s': %s",
                intento, MAX_REINTENTOS, consulta, e,
            )
            time.sleep(ESPERA_ENTRE_PETICIONES * intento)

    logger.error("No se pudo geocodificar tras %d intentos: %s", MAX_REINTENTOS, consulta)
    return None

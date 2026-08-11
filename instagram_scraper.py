"""
instagram_scraper.py
---------------------
Scraper "best-effort" de publicaciones públicas de Instagram.

ADVERTENCIA IMPORTANTE (léela antes de usar en producción):
Instagram no ofrece una API pública gratuita para leer cuentas que no
administras. Este módulo usa `instaloader` para leer perfiles PÚBLICOS
sin iniciar sesión. Es funcional hoy, pero:
  - Meta cambia su HTML/JSON interno sin aviso -> puede romperse.
  - Instagram limita o bloquea IPs que hacen muchas peticiones seguidas.
  - Usar esto de forma intensiva puede violar los Términos de Servicio
    de Meta. Úsalo con una frecuencia razonable (el workflow de GitHub
    Actions incluido corre cada pocas horas, no cada minuto).

Diseño defensivo:
  - Cada cuenta se procesa de forma AISLADA: si una falla, no tumba
    a las demás.
  - Reintentos con backoff exponencial.
  - Caché en disco: si Instagram bloquea la petición, se usa la última
    copia buena conocida en vez de romper el pipeline.
  - Límite de posts recientes por cuenta para no sobrecargar.
"""

from __future__ import annotations

import json
import logging
import time
import random
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger("scraper")

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

MAX_POSTS_PER_CUENTA = 12          # no bajar más para no perder eventos, no subir para no forzar el rate limit
MAX_REINTENTOS = 3
ESPERA_BASE_SEGUNDOS = 4           # backoff exponencial: 4s, 8s, 16s...
ESPERA_ENTRE_CUENTAS_SEGUNDOS = (6, 14)  # rango aleatorio para no parecer un bot agresivo


@dataclass
class PublicacionCruda:
    institucion_id: str
    institucion_nombre: str
    shortcode: str
    url: str
    texto: str
    fecha_publicacion: str  # ISO 8601
    es_video: bool


def _ruta_cache(institucion_id: str) -> Path:
    return CACHE_DIR / f"{institucion_id}.json"


def _guardar_cache(institucion_id: str, publicaciones: list[PublicacionCruda]) -> None:
    data = [asdict(p) for p in publicaciones]
    _ruta_cache(institucion_id).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _leer_cache(institucion_id: str) -> list[PublicacionCruda]:
    ruta = _ruta_cache(institucion_id)
    if not ruta.exists():
        return []
    try:
        data = json.loads(ruta.read_text(encoding="utf-8"))
        return [PublicacionCruda(**item) for item in data]
    except Exception as e:
        logger.warning("Caché corrupta para %s, se ignora: %s", institucion_id, e)
        return []


def _scrape_perfil_con_instaloader(username: str, limite: int) -> list[dict]:
    """
    Intenta obtener publicaciones públicas recientes con instaloader.
    Lanza excepción si algo falla; el llamador decide qué hacer.
    """
    import instaloader  # import perezoso: si la librería no está o falla, no tumba el resto del módulo

    L = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        quiet=True,
    )

    profile = instaloader.Profile.from_username(L.context, username)

    if profile.is_private:
        raise RuntimeError(f"@{username} es una cuenta privada; no se puede leer sin autorización.")

    posts = []
    for i, post in enumerate(profile.get_posts()):
        if i >= limite:
            break
        posts.append({
            "shortcode": post.shortcode,
            "url": f"https://www.instagram.com/p/{post.shortcode}/",
            "texto": post.caption or "",
            "fecha_publicacion": post.date_utc.isoformat(),
            "es_video": post.is_video,
        })
    return posts


def obtener_publicaciones_institucion(institucion: dict) -> list[PublicacionCruda]:
    """
    Punto de entrada principal. Nunca lanza excepción hacia afuera:
    en el peor caso devuelve la caché (o una lista vacía).
    """
    username = institucion["instagram"]
    institucion_id = institucion["id"]
    nombre = institucion["nombre"]

    ultimo_error: Optional[Exception] = None

    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            crudos = _scrape_perfil_con_instaloader(username, MAX_POSTS_PER_CUENTA)
            publicaciones = [
                PublicacionCruda(
                    institucion_id=institucion_id,
                    institucion_nombre=nombre,
                    shortcode=p["shortcode"],
                    url=p["url"],
                    texto=p["texto"],
                    fecha_publicacion=p["fecha_publicacion"],
                    es_video=p["es_video"],
                )
                for p in crudos
            ]
            _guardar_cache(institucion_id, publicaciones)
            logger.info("OK @%s: %d publicaciones obtenidas", username, len(publicaciones))
            return publicaciones

        except ImportError:
            logger.error(
                "instaloader no está instalado. Ejecuta: pip install instaloader --break-system-packages"
            )
            break  # no tiene sentido reintentar si falta la librería

        except Exception as e:
            ultimo_error = e
            espera = ESPERA_BASE_SEGUNDOS * (2 ** (intento - 1))
            logger.warning(
                "Intento %d/%d falló para @%s (%s). Reintentando en %ds...",
                intento, MAX_REINTENTOS, username, e, espera,
            )
            time.sleep(espera)

    logger.error(
        "No se pudo obtener @%s tras %d intentos (%s). Usando caché local si existe.",
        username, MAX_REINTENTOS, ultimo_error,
    )
    return _leer_cache(institucion_id)


def obtener_todas(instituciones: list[dict]) -> dict[str, list[PublicacionCruda]]:
    """
    Recorre todas las instituciones de forma aislada: un fallo en una
    cuenta jamás detiene el procesamiento de las demás.
    Incluye pausas aleatorias entre cuentas para reducir el riesgo de bloqueo.
    """
    resultados: dict[str, list[PublicacionCruda]] = {}
    for i, inst in enumerate(instituciones):
        try:
            resultados[inst["id"]] = obtener_publicaciones_institucion(inst)
        except Exception as e:
            # Red de seguridad final: pase lo que pase, nunca tumbar el pipeline completo.
            logger.error("Fallo inesperado y no controlado con %s: %s", inst["id"], e)
            resultados[inst["id"]] = _leer_cache(inst["id"])

        if i < len(instituciones) - 1:
            time.sleep(random.uniform(*ESPERA_ENTRE_CUENTAS_SEGUNDOS))

    return resultados

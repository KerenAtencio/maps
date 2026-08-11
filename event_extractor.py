# -*- coding: utf-8 -*-
"""
event_extractor.py
-------------------
Analiza el texto (caption) de una publicación y decide:
  1. ¿Es un evento? (coincide con alguna palabra clave / sinónimo)
  2. ¿Qué dirección menciona? (para luego geocodificar)
  3. ¿Qué fecha y hora tiene?
  4. Un nombre/título limpio para mostrar en el mapa.

Es deliberadamente conservador: prefiere no marcar un texto como evento
antes que inventar datos. Todo lo que no se puede extraer queda como
None y se maneja explícitamente aguas abajo (nunca se inventa una
dirección o coordenada).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# 1. Palabras clave / sinónimos de "evento" en español (Colombia)
# ---------------------------------------------------------------------------
PALABRAS_CLAVE_EVENTO = [
    r"evento", r"eventos",
    r"reuni[oó]n", r"reuni[oó]n(?:es)?",
    r"conferencia", r"congreso",
    r"taller(?:es)?",
    r"seminario",
    r"foro",
    r"capacitaci[oó]n",
    r"jornada(?:s)?",
    r"feria",
    r"convocatoria",
    r"inauguraci[oó]n",
    r"lanzamiento",
    r"encuentro",
    r"webinar",
    r"charla",
    r"panel",
    r"cumbre",
    r"celebraci[oó]n",
    r"festival",
    r"exposici[oó]n",
    r"rueda de prensa",
    r"rueda de negocios",
    r"asamblea",
    r"audiencia p[uú]blica",
    r"consejo de seguridad",
    r"c[ií]rculo de conversaci[oó]n",
    r"campa[ñn]a",
    r"brigada",
    r"jornada de salud",
    r"open house",
    r"casa abierta",
    r"desfile",
    r"concierto",
    r"vacunaci[oó]n",
]
_RE_PALABRA_CLAVE = re.compile(
    r"\b(" + "|".join(PALABRAS_CLAVE_EVENTO) + r")\b", re.IGNORECASE
)

# Palabras que casi siempre indican que el post NO es una convocatoria a
# evento real (avisos, felicitaciones, resultados, etc.) — reduce falsos positivos.
_RE_EXCLUSION = re.compile(
    r"\b(feliz cumplea[ñn]os|en memoria de|lamentamos|luto|condolencias|"
    r"resultados del sorteo|gan[oó] el sorteo)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# 2. Extracción de dirección
# ---------------------------------------------------------------------------
# Vías típicas de nomenclatura urbana colombiana: Calle, Carrera, Avenida,
# Diagonal, Transversal, Circular, Autopista + número (+ complemento # nn-nn)
_RE_DIRECCION = re.compile(
    r"""
    (
        (?:calle|cl|carrera|cra|kra|avenida|av|diagonal|dg|transversal|tv|
           circular|autopista|manzana|mz)
        \.?\s*\d{1,3}\s?[a-zA-Z]?
        (?:\s*(?:bis)?\s*(?:\#|no\.?|número|numero)?\s*\d{1,3}[a-zA-Z]?\s*-\s*\d{1,3})?
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Lugares conocidos de Valledupar que suelen aparecer sin nomenclatura numérica
LUGARES_CONOCIDOS = [
    "parque de la leyenda vallenata", "plaza alfonso lópez", "plaza alfonso lopez",
    "centro de convenciones", "coliseo de ferias", "estadio armando maestre pavajeau",
    "parque de la provincia", "malecón del guatapurí", "malecon del guatapuri",
    "biblioteca departamental", "catedral de valledupar", "terminal de transportes",
    "aeropuerto alfonso lópez pumarejo", "mercado público", "galería popular",
    "universidad popular del cesar", "villa del río", "sena regional cesar",
]
_RE_LUGAR_CONOCIDO = re.compile(
    r"\b(" + "|".join(re.escape(l) for l in LUGARES_CONOCIDOS) + r")\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# 3. Extracción de hora
# ---------------------------------------------------------------------------
_RE_HORA = re.compile(
    r"""
    \b(
        (?:[01]?\d|2[0-3])          # hora 0-23 o 1-12
        (?::[0-5]\d)?               # minutos opcionales
        \s*
        (?:am|pm|a\.m\.?|p\.m\.?)?  # am/pm opcional
    )\s*(?:hrs?|horas)?\b
    """,
    re.IGNORECASE | re.VERBOSE,
)
# Frases que suelen preceder la hora real del evento (para descartar horas
# que en realidad son parte de un número de teléfono u otro dato)
_RE_CONTEXTO_HORA = re.compile(
    r"(?:hora|horario|a las|desde las|inicia(?:mos)?|comenzamos)\D{0,15}"
    r"((?:[01]?\d|2[0-3])(?::[0-5]\d)?\s*(?:am|pm|a\.m\.?|p\.m\.?)?)",
    re.IGNORECASE,
)

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
_RE_FECHA_TEXTO = re.compile(
    r"\b(\d{1,2})\s+de\s+(" + "|".join(MESES.keys()) + r")(?:\s+de\s+(\d{4}))?\b",
    re.IGNORECASE,
)
_RE_FECHA_NUMERICA = re.compile(r"\b(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?\b")


@dataclass
class EventoExtraido:
    es_evento: bool
    titulo: str
    direccion_texto: Optional[str]
    fecha_texto: Optional[str]      # tal como aparece / se infiere, para mostrar
    fecha_iso: Optional[str]        # normalizada si se pudo inferir el año
    hora_texto: Optional[str]
    palabra_clave_detectada: Optional[str]


def _limpiar_titulo(texto: str, palabra_clave: str, max_len: int = 90) -> str:
    """
    Genera un título corto y legible a partir del caption completo, ya que
    los captions de Instagram suelen ser largos y con hashtags.
    """
    # Nos quedamos con la primera línea/frase que sea sustanciosa,
    # descartando hashtags y menciones sueltas.
    lineas = [l.strip() for l in texto.splitlines() if l.strip()]
    candidata = ""
    for linea in lineas:
        limpia = re.sub(r"[#@]\S+", "", linea).strip()
        if len(limpia) > 15:
            candidata = limpia
            break
    if not candidata:
        candidata = re.sub(r"[#@]\S+", "", texto).strip()

    candidata = re.sub(r"\s+", " ", candidata)
    if len(candidata) > max_len:
        candidata = candidata[:max_len].rsplit(" ", 1)[0] + "…"
    return candidata or f"{palabra_clave.capitalize()} (sin título claro)"


def _extraer_direccion(texto: str) -> Optional[str]:
    m = _RE_DIRECCION.search(texto)
    if m:
        return m.group(1).strip()
    m = _RE_LUGAR_CONOCIDO.search(texto)
    if m:
        return m.group(1).strip() + ", Valledupar, Cesar"
    return None


def _extraer_hora(texto: str) -> Optional[str]:
    m = _RE_CONTEXTO_HORA.search(texto)
    if m:
        return m.group(1).strip()
    m = _RE_HORA.search(texto)
    if m:
        return m.group(1).strip()
    return None


def _extraer_fecha(texto: str, fecha_publicacion_iso: str) -> tuple[Optional[str], Optional[str]]:
    """
    Devuelve (fecha_texto_legible, fecha_iso_normalizada) si se pudo inferir.
    Si el post no menciona una fecha explícita, se asume que el evento es el
    mismo día de la publicación (comportamiento típico en estas cuentas).
    """
    m = _RE_FECHA_TEXTO.search(texto)
    if m:
        dia, mes_nombre, anio = m.groups()
        mes = MESES[mes_nombre.lower()]
        anio = int(anio) if anio else datetime.fromisoformat(fecha_publicacion_iso).year
        try:
            fecha_iso = datetime(anio, mes, int(dia)).date().isoformat()
            return f"{dia} de {mes_nombre} de {anio}", fecha_iso
        except ValueError:
            pass

    m = _RE_FECHA_NUMERICA.search(texto)
    if m:
        dia, mes, anio = m.groups()
        anio = int(anio) if anio else datetime.fromisoformat(fecha_publicacion_iso).year
        if anio < 100:
            anio += 2000
        try:
            fecha_iso = datetime(anio, int(mes), int(dia)).date().isoformat()
            return f"{dia}/{mes}/{anio}", fecha_iso
        except ValueError:
            pass

    # sin fecha explícita -> se asume el día de publicación
    fecha_pub = datetime.fromisoformat(fecha_publicacion_iso).date()
    return None, fecha_pub.isoformat()


def analizar_publicacion(texto: str, fecha_publicacion_iso: str) -> EventoExtraido:
    if not texto or _RE_EXCLUSION.search(texto):
        return EventoExtraido(False, "", None, None, None, None, None)

    m_clave = _RE_PALABRA_CLAVE.search(texto)
    if not m_clave:
        return EventoExtraido(False, "", None, None, None, None, None)

    palabra_clave = m_clave.group(1)
    titulo = _limpiar_titulo(texto, palabra_clave)
    direccion = _extraer_direccion(texto)
    hora = _extraer_hora(texto)
    fecha_texto, fecha_iso = _extraer_fecha(texto, fecha_publicacion_iso)

    return EventoExtraido(
        es_evento=True,
        titulo=titulo,
        direccion_texto=direccion,
        fecha_texto=fecha_texto,
        fecha_iso=fecha_iso,
        hora_texto=hora,
        palabra_clave_detectada=palabra_clave,
    )

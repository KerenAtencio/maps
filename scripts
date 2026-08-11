# -*- coding: utf-8 -*-
"""
generate_qr.py
--------------
Genera un QR en alta resolución, listo para imprimir en volantes o carteles,
apuntando a la URL pública del mapa (GitHub Pages).

Uso:
    python scripts/generate_qr.py https://tu-usuario.github.io/valledupar-eventos/

Requiere:
    pip install qrcode[pil] --break-system-packages
"""

import sys
from pathlib import Path

import qrcode
from qrcode.constants import ERROR_CORRECT_H

SALIDA_DIR = Path(__file__).resolve().parent.parent / "docs" / "assets"
SALIDA_DIR.mkdir(parents=True, exist_ok=True)

# Colores de marca: fondo blanco puro (mejor para impresión), módulos en
# el verde-noche de la identidad visual, para que el QR combine con el
# material impreso sin perder contraste/legibilidad de escaneo.
COLOR_MODULOS = "#0F2E33"
COLOR_FONDO = "#FFFFFF"


def generar(url: str) -> None:
    qr = qrcode.QRCode(
        version=None,                 # tamaño automático según la longitud de la URL
        error_correction=ERROR_CORRECT_H,  # máxima corrección de errores: soporta logo superpuesto y desgaste de impresión
        box_size=30,                  # tamaño de cada módulo en píxeles -> imagen final grande, apta para imprimir
        border=4,                     # margen blanco reglamentario alrededor del QR
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color=COLOR_MODULOS, back_color=COLOR_FONDO)

    ruta_png = SALIDA_DIR / "qr_mapa_eventos.png"
    img.save(ruta_png)

    # Versión SVG (vectorial), ideal para imprenta profesional a cualquier tamaño
    try:
        from qrcode.image.svg import SvgPathImage
        qr_svg = qrcode.make(url, image_factory=SvgPathImage, error_correction=ERROR_CORRECT_H)
        ruta_svg = SALIDA_DIR / "qr_mapa_eventos.svg"
        qr_svg.save(str(ruta_svg))
        print(f"QR vectorial guardado en: {ruta_svg}")
    except ImportError:
        print("(Instala 'qrcode[pil]' completo para también obtener el SVG vectorial)")

    print(f"QR en alta resolución guardado en: {ruta_png}")
    print(f"Apunta a: {url}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python scripts/generate_qr.py <URL-del-mapa-publicado>")
        print("Ejemplo: python scripts/generate_qr.py https://tu-usuario.github.io/valledupar-eventos/")
        sys.exit(1)
    generar(sys.argv[1])

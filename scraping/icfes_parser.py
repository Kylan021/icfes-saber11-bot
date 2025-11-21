from bs4 import BeautifulSoup

"""
Este módulo recibe el HTML obtenido por icfes_client.py y extrae:

- Nombre del estudiante
- Puntaje general
- Percentil general
- Puntaje por prueba
- Percentil por prueba

Diseñado para ser resistente a cambios menores en el DOM del ICFES.
"""


def _safe_text(element):
    """Devuelve el texto limpio de un elemento o None si no existe."""
    if element:
        return element.get_text(strip=True)
    return None


def _extract_number(text):
    """Convierte texto a número entero si es posible."""
    if not text:
        return None
    try:
        return int(text.replace('.', '').strip())
    except:
        return None


def parse_icfes_results(html: str) -> dict:
    """
    Extrae el nombre del estudiante, puntaje general,
    percentil general, puntajes y percentiles por prueba.
    """

    soup = BeautifulSoup(html, "html.parser")
    data = {}

    name_button = soup.select_one("icfes-navbar button")
    data["nombre_estudiante"] = _safe_text(name_button)

    puntaje_general = soup.select_one(
        "icfes-puntaje-general div div div span"
    )
    data["puntaje_general"] = _extract_number(_safe_text(puntaje_general))

    percentil_general = soup.select_one(
        "icfes-puntaje-general div div div div span"
    )
    data["percentil_general"] = _extract_number(_safe_text(percentil_general))

    pruebas = [
        ("lectura_critica", 2),
        ("matematicas", 3),
        ("sociales", 4),
        ("ciencias_naturales", 5),
        ("ingles", 6),
    ]

    for nombre, index in pruebas:

        # Selector de la tarjeta correspondiente
        tarjeta = soup.select_one(
            f"icfes-puntaje-pruebas div div div:nth-of-type({index})"
        )

        if not tarjeta:
            data[f"puntaje_{nombre}"] = None
            data[f"percentil_{nombre}"] = None
            continue

        # Puntaje → normalmente span principal
        puntaje = tarjeta.select_one("div div div span")
        data[f"puntaje_{nombre}"] = _extract_number(_safe_text(puntaje))

        # Percentil → span más interno
        percentil = tarjeta.select_one("div div div div span")
        data[f"percentil_{nombre}"] = _extract_number(_safe_text(percentil))

    return data


def parse_all(html: str) -> dict:
    """
    Punto único de entrada externo.
    """
    return parse_icfes_results(html)

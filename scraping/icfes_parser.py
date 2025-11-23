from bs4 import BeautifulSoup
import re


def _safe_text(element):
    return element.get_text(strip=True) if element else None


def _extract_number(text):
    if not text:
        return None
    try:
        clean = re.sub(r"[^\d]", "", str(text))
        return int(clean) if clean else None
    except Exception:
        return None


def parse_icfes_results(html: str, percentiles_area: dict = None) -> dict:
    """
    Parsea el HTML de Resultados Saber 11 del ICFES.

    - Nombre del estudiante (navbar, span.nombreCompleto)
    - Puntaje general
    - Percentil general
    - Puntaje y percentil por cada prueba
    """
    soup = BeautifulSoup(html, "html.parser")
    data = {}

    nombre_span = soup.select_one("span.nombreCompleto")
    data["nombre_estudiante"] = _safe_text(nombre_span)

    puntaje_general_elem = soup.select_one("icfes-puntaje-general span.superior")
    if not puntaje_general_elem:
       
        puntaje_general_elem = soup.select_one(".superior")
    data["puntaje_general"] = _extract_number(_safe_text(puntaje_general_elem))

    percentil_general_elem = soup.select_one(".texto-puntaje-principal")
    if not percentil_general_elem:
        
        percentil_general_elem = soup.select_one(".escalar")
    data["percentil_general"] = _extract_number(_safe_text(percentil_general_elem))

    areas = {
        "lectura_critica": "Lectura Crítica",
        "matematicas": "Matemáticas",
        "sociales": "Sociales y Ciudadanas",
        "ciencias_naturales": "Ciencias Naturales",
        "ingles": "Inglés",
    }

    for key, label in areas.items():

        fila = soup.find(
            "span",
            class_="title-tab",
            string=re.compile(label, re.IGNORECASE),
        )
        if fila:
            enlace = fila.find_parent("a")
            puntaje_elem = enlace.select_one(".superior") if enlace else None
            data[f"puntaje_{key}"] = _extract_number(_safe_text(puntaje_elem))
        else:
            data[f"puntaje_{key}"] = None

        if percentiles_area and f"percentil_{key}" in percentiles_area:
            data[f"percentil_{key}"] = percentiles_area[f"percentil_{key}"]
            continue

        area_label_p = soup.find(
            "p",
            class_="text-color-black",
            string=re.compile(label, re.IGNORECASE),
        )
        if area_label_p:
            escalar_elem = area_label_p.find_next("span", class_="escalar")
            data[f"percentil_{key}"] = _extract_number(_safe_text(escalar_elem))
        else:
            data[f"percentil_{key}"] = None

    return data


def parse_all(html: str, percentiles_area: dict = None) -> dict:
    try:
        return parse_icfes_results(html, percentiles_area)
    except Exception as e:
        print(f"Error en parsing: {e}")
        return {
            "nombre_estudiante": None,
            "puntaje_general": None,
            "percentil_general": None,
            "error_parsing": str(e),
        }

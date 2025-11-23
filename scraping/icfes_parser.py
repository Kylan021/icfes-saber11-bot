from bs4 import BeautifulSoup
import re


def _safe_text(element):
    return element.get_text(strip=True) if element else None


def _extract_int(text):
    if not text:
        return None
    cleaned = re.sub(r"[^0-9]", "", str(text))
    return int(cleaned) if cleaned else None


def parse_icfes_results(html: str, percentiles_area: dict | None = None) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    data = {}

    nombre = soup.select_one("span.nombreCompleto")
    data["nombre_estudiante"] = _safe_text(nombre)

    puntaje_general = None
    comp_general = soup.find("icfes-puntaje-general")
    if comp_general:
        span_pg = comp_general.find("span", class_="texto-puntaje-principal")
        puntaje_general = _extract_int(_safe_text(span_pg))

    if puntaje_general is None:
        span_pg = soup.find("span", class_="texto-puntaje-principal")
        puntaje_general = _extract_int(_safe_text(span_pg))

    data["puntaje_general"] = puntaje_general

    percentil_general = None
    label = soup.find("span", class_="texto",
                      string=re.compile("Estudiantes a nivel nacional", re.IGNORECASE))
    if label:
        container = label.parent
        sibling = container.find_next_sibling()
        while sibling and percentil_general is None:
            pct_span = sibling.find("span", class_="texto-puntaje-principal")
            if pct_span:
                percentil_general = _extract_int(_safe_text(pct_span))
                break
            sibling = sibling.find_next_sibling()

    data["percentil_general"] = percentil_general

    areas = {
        "lectura_critica": "Lectura Crítica",
        "matematicas": "Matemáticas",
        "sociales": "Sociales y Ciudadanas",
        "ciencias_naturales": "Ciencias Naturales",
        "ingles": "Inglés",
    }

    for key, label in areas.items():

        puntaje_area = None
        tab = soup.find("span", class_="title-tab",
                        string=re.compile(label, re.IGNORECASE))
        if tab:
            link = tab.find_parent("a")
            if link:
                val = link.find("span", class_="superior")
                puntaje_area = _extract_int(_safe_text(val))

        data[f"puntaje_{key}"] = puntaje_area

        if percentiles_area and f"percentil_{key}" in percentiles_area:
            data[f"percentil_{key}"] = percentiles_area[f"percentil_{key}"]
            continue

        # Buscar percentil debajo del texto del área
        p_area = soup.find("p", class_="text-color-black",
                           string=re.compile(label, re.IGNORECASE))
        if p_area:
            escalar = p_area.find_next("span", class_="escalar")
            data[f"percentil_{key}"] = _extract_int(_safe_text(escalar))
        else:
            data[f"percentil_{key}"] = None

    return data


def parse_all(html: str, percentiles_area: dict | None = None) -> dict:
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

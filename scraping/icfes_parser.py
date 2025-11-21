from bs4 import BeautifulSoup
import re

"""
Parser mejorado con múltiples estrategias de extracción
"""


def _safe_text(element):
    """Devuelve el texto limpio de un elemento o None si no existe."""
    if element:
        text = element.get_text(strip=True)
        return text if text else None
    return None


def _extract_number(text):
    """Convierte texto a número entero si es posible."""
    if not text:
        return None
    try:
        # Remover puntos y comas, mantener solo dígitos
        clean = re.sub(r'[^\d]', '', str(text))
        return int(clean) if clean else None
    except:
        return None


def _find_text_with_patterns(soup, patterns):
    """
    Busca texto en el HTML usando múltiples patrones regex.
    """
    for pattern in patterns:
        for element in soup.find_all(string=re.compile(pattern, re.IGNORECASE)):
            parent = element.parent
            # Buscar el número en el elemento o sus hermanos
            number_text = parent.get_text(strip=True)
            number = _extract_number(number_text)
            if number:
                return number
    return None


def parse_icfes_results(html: str) -> dict:
    """
    Extrae información de resultados ICFES con múltiples estrategias.
    """
    soup = BeautifulSoup(html, "html.parser")
    data = {}

    # ========== NOMBRE DEL ESTUDIANTE ==========
    # Estrategia 1: Buscar en navbar button
    name_button = soup.select_one("icfes-navbar button")
    if name_button:
        data["nombre_estudiante"] = _safe_text(name_button)
    
    # Estrategia 2: Buscar por texto "Bienvenido"
    if not data.get("nombre_estudiante"):
        welcome = soup.find(string=re.compile(r'Bienvenid[oa]', re.IGNORECASE))
        if welcome:
            data["nombre_estudiante"] = _safe_text(welcome.parent)

    # ========== PUNTAJE GENERAL ==========
    # Buscar por múltiples selectores
    selectors_puntaje = [
        "icfes-puntaje-general div div div div div span",
        ".puntaje-general",
        "[class*='puntaje'][class*='general']",
    ]
    
    for selector in selectors_puntaje:
        element = soup.select_one(selector)
        if element:
            data["puntaje_general"] = _extract_number(_safe_text(element))
            if data["puntaje_general"]:
                break
    
    # Buscar por patrones de texto
    if not data.get("puntaje_general"):
        data["puntaje_general"] = _find_text_with_patterns(
            soup, 
            [r'puntaje\s*global', r'puntaje\s*general', r'puntaje\s*total']
        )

    # ========== PERCENTIL GENERAL ==========
    selectors_percentil = [
        "icfes-puntaje-general div div div div div div div[1] div[1] div[2] span",
        ".percentil-general",
        "[class*='percentil'][class*='general']",
    ]
    
    for selector in selectors_percentil:
        element = soup.select_one(selector)
        if element:
            data["percentil_general"] = _extract_number(_safe_text(element))
            if data["percentil_general"]:
                break

    if not data.get("percentil_general"):
        data["percentil_general"] = _find_text_with_patterns(
            soup,
            [r'percentil\s*global', r'percentil\s*general']
        )

    # ========== PUNTAJES POR PRUEBA ==========
    pruebas = [
        ("lectura_critica", ["lectura", "crítica", "reading"]),
        ("matematicas", ["matemática", "mathematics"]),
        ("sociales", ["sociales", "ciudadanas", "social"]),
        ("ciencias_naturales", ["ciencias", "naturales", "science"]),
        ("ingles", ["inglés", "english", "ingles"]),
    ]

    for nombre, keywords in pruebas:
        # Inicializar con None
        data[f"puntaje_{nombre}"] = None
        data[f"percentil_{nombre}"] = None
        
        # Buscar sección de la prueba
        for keyword in keywords:
            section = soup.find(string=re.compile(keyword, re.IGNORECASE))
            if section:
                # Buscar números en el contexto cercano
                container = section.find_parent(['div', 'td', 'li'])
                if container:
                    # Buscar todos los números en el contenedor
                    numbers = []
                    for elem in container.find_all(['span', 'div', 'strong']):
                        num = _extract_number(_safe_text(elem))
                        if num:
                            numbers.append(num)
                    
                    # Usualmente: primer número = puntaje, segundo = percentil
                    if len(numbers) >= 1:
                        data[f"puntaje_{nombre}"] = numbers[0]
                    if len(numbers) >= 2:
                        data[f"percentil_{nombre}"] = numbers[1]
                    break

    return data


def parse_all(html: str) -> dict:
    """
    Punto único de entrada externo.
    """
    try:
        return parse_icfes_results(html)
    except Exception as e:
        print(f"❌ Error en parsing: {e}")
        return {
            "nombre_estudiante": None,
            "puntaje_general": None,
            "percentil_general": None,
            "error_parsing": str(e)
        }
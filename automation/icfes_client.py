from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
import time
import base64
import requests

from playwright.sync_api import sync_playwright, Page, expect

from config import ICFES_LOGIN_URL, HEADLESS, SCREENSHOT_DIR, ANTI_CAPTCHA_KEY


@dataclass
class LoginParams:
    """Parámetros necesarios para hacer la consulta de resultados."""
    tipo_documento: str
    numero_documento: str
    fecha_nacimiento: str  # puede venir como DD/MM/YYYY o YYYY-MM-DD


@dataclass
class FetchResult:
    """Resultado de la automatización: HTML y ruta del pantallazo (si aplica)."""
    html: str
    screenshot_path: Optional[Path] = None


def _normalizar_fecha(fecha_str: str) -> str:
    """
    Normaliza la fecha de nacimiento a formato YYYY-MM-DD para <input type="date">.

    - Si viene como 'DD/MM/YYYY', la convierte.
    - Si ya viene como 'YYYY-MM-DD', la deja igual.
    - Si no se puede parsear, devuelve el string original.
    """
    fecha_str = fecha_str.strip()
    if not fecha_str:
        return fecha_str

    # Si ya parece estar en formato HTML5 (YYYY-MM-DD)
    if "-" in fecha_str and len(fecha_str) == 10:
        return fecha_str

    # Intentar convertir desde DD/MM/YYYY
    try:
        dt = datetime.strptime(fecha_str, "%d/%m/%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        # Si falla el parseo, devolvemos tal cual
        return fecha_str


def _fill_login_form(page: Page, params: LoginParams) -> None:
    """
    Llena el formulario de login en la página del ICFES.

    Basado en el HTML actual del login:
      - Tipo de documento:  select[formcontrolname="tipoDocumento"]
      - Número de documento: input#identificacion
      - Fecha de nacimiento: input#fechaNacimiento (type="date", formato YYYY-MM-DD)
    """
    # Esperar a que el formulario esté cargado
    page.wait_for_selector("form")

    # Tipo de documento (si existe el combo)
    try:
        tipo_doc_select = page.locator('select[formcontrolname="tipoDocumento"]')
        if tipo_doc_select.count() > 0:
            tipo_doc_select.select_option(params.tipo_documento)
    except Exception as e:
        # No es crítico: el backend validará si falta
        print(f"Advertencia al seleccionar tipo de documento: {e}")

    # Llenar número de documento
    page.fill("#identificacion", params.numero_documento)

    # Normalizar y llenar fecha de nacimiento
    fecha_normalizada = _normalizar_fecha(params.fecha_nacimiento)
    page.fill("#fechaNacimiento", fecha_normalizada)

    # Pequeña pausa para que Angular procese cambios de formulario
    time.sleep(0.5)


def _solve_captcha_with_anticaptcha(page: Page) -> None:
    """
    Resuelve el reCAPTCHA usando el servicio Anti-Captcha.
    
    Detecta el sitekey de reCAPTCHA en la página y utiliza la API de Anti-Captcha
    para obtener el token de solución.
    """
    if not ANTI_CAPTCHA_KEY or ANTI_CAPTCHA_KEY.startswith("PON_AQUI"):
        raise RuntimeError(
            "No se ha configurado ANTI_CAPTCHA_KEY. "
            "Define la key en variables de entorno o en config.py para usar Anti-Captcha."
        )

    # Verificar si hay reCAPTCHA en la página
    recaptcha_frame = page.frame_locator('iframe[src*="recaptcha"]').first
    if recaptcha_frame.count() == 0:
        print("No se encontró reCAPTCHA en la página, continuando...")
        return

    # Obtener el sitekey del reCAPTCHA
    sitekey = page.get_attribute('div[class*="recaptcha"]', "data-sitekey")
    if not sitekey:
        # Intentar encontrar el sitekey de otras formas
        sitekey_element = page.locator('[data-sitekey]').first
        if sitekey_element.count() > 0:
            sitekey = sitekey_element.get_attribute("data-sitekey")
        else:
            # Buscar en scripts
            sitekey_script = page.locator('script:contains("sitekey")').first
            if sitekey_script.count() > 0:
                script_content = sitekey_script.text_content()
                import re
                sitekey_match = re.search(r'sitekey["\']?\s*:\s*["\']([^"\']+)["\']', script_content)
                if sitekey_match:
                    sitekey = sitekey_match.group(1)

    if not sitekey:
        raise RuntimeError("No se pudo detectar el sitekey de reCAPTCHA")

    print(f"Sitekey detectado: {sitekey}")

    # Obtener la URL actual para el parámetro pageurl
    pageurl = page.url

    # Crear tarea de reCAPTCHA v2 sin proxy
    from urllib.parse import urlparse
    
    # Preparar datos para la API de Anti-Captcha
    task_data = {
        "clientKey": ANTI_CAPTCHA_KEY,
        "task": {
            "type": "RecaptchaV2TaskProxyless",
            "websiteURL": pageurl,
            "websiteKey": sitekey
        }
    }

    print("Enviando tarea a Anti-Captcha...")
    
    # Crear la tarea
    create_task_url = "https://api.anti-captcha.com/createTask"
    create_response = requests.post(create_task_url, json=task_data)
    create_result = create_response.json()

    if create_result.get("errorId") != 0:
        error_code = create_result.get("errorCode", "UNKNOWN")
        error_desc = create_result.get("errorDescription", "Error desconocido")
        raise RuntimeError(f"Error de Anti-Captcha al crear tarea: {error_code} - {error_desc}")

    task_id = create_result["taskId"]
    print(f"Tarea creada con ID: {task_id}")

    # Esperar por la solución
    get_result_url = "https://api.anti-captcha.com/getTaskResult"
    get_result_data = {
        "clientKey": ANTI_CAPTCHA_KEY,
        "taskId": task_id
    }

    max_attempts = 60  # Máximo 2 minutos (2 segundos por intento)
    for attempt in range(max_attempts):
        time.sleep(2)  # Esperar 2 segundos entre intentos
        
        get_response = requests.post(get_result_url, json=get_result_data)
        result = get_response.json()

        if result.get("errorId") != 0:
            error_code = result.get("errorCode", "UNKNOWN")
            error_desc = result.get("errorDescription", "Error desconocido")
            raise RuntimeError(f"Error de Anti-Captcha al obtener resultado: {error_code} - {error_desc}")

        status = result.get("status", "processing")
        
        if status == "ready":
            # Solución obtenida
            solution = result["solution"]["gRecaptchaResponse"]
            print("reCAPTCHA resuelto exitosamente")
            
            # Inyectar el token en la página
            page.evaluate(f"""
            (function() {{
                // Buscar el textarea del recaptcha
                const textarea = document.querySelector('#g-recaptcha-response');
                if (textarea) {{
                    textarea.value = '{solution}';
                    textarea.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }}
                
                // También intentar con el campo hidden si existe
                const hiddenField = document.querySelector('input[name="g-recaptcha-response"]');
                if (hiddenField) {{
                    hiddenField.value = '{solution}';
                    hiddenField.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }}
                
                // Disparar eventos para notificar a reCAPTCHA
                const event = new Event('recaptcha-callback', {{ bubbles: true }});
                document.dispatchEvent(event);
                
                console.log('Token de reCAPTCHA inyectado');
            }})();
            """)
            
            # Esperar un momento para que se procese
            time.sleep(1)
            return

        elif status == "processing":
            print(f"Esperando solución... ({attempt + 1}/{max_attempts})")
            continue

    raise RuntimeError("Tiempo de espera agotado para resolver el reCAPTCHA")



def _submit_form_and_wait_results(page: Page) -> None:
    """
    Envía el formulario y espera a que cargue la página de resultados.
    """
    # Hacer clic en el botón de consultar (Ingresar)
    page.click("button[type='submit']")

    # Esperar a que la página cambie (ya sea a resultados o a error)
    try:
        page.wait_for_load_state("networkidle")
        time.sleep(3)

        # Verificar si estamos en una página con posibles resultados
        resultados_selector = "table, .resultados, .score, .puntaje, [class*='result']"
        page.wait_for_selector(resultados_selector, timeout=10000)

    except Exception as e:
        print(f"Espera de resultados falló: {e}")
        # Verificar si hay mensaje de error visible
        error_selectors = [".error", ".alert-danger", "[class*='error']", "[class*='alert']"]
        for selector in error_selectors:
            loc = page.locator(selector)
            if loc.count() > 0 and loc.first.is_visible():
                error_text = loc.first.text_content()
                raise RuntimeError(f"Error en el formulario: {error_text}")
        # Si no hay error visible, continuar con el HTML actual


def _take_results_screenshot(page: Page, numero_documento: str) -> Path:
    """
    Toma un pantallazo de la página de resultados y devuelve la ruta.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{numero_documento}_{timestamp}.png"
    path = SCREENSHOT_DIR / filename
    page.screenshot(path=str(path), full_page=True)
    return path


def _handle_possible_errors(page: Page) -> None:
    """
    Maneja posibles errores o mensajes en la página.
    """
    # Verificar mensajes de error comunes
    error_selectors = [
        ".error",
        ".alert-danger",
        ".text-danger",
        "[class*='error']",
        "[class*='alert']",
    ]

    for selector in error_selectors:
        elements = page.locator(selector)
        if elements.count() > 0:
            for i in range(elements.count()):
                error_element = elements.nth(i)
                if error_element.is_visible():
                    error_text = (error_element.text_content() or "").strip()
                    if error_text and len(error_text) > 5:
                        print(f"Advertencia/Error detectado: {error_text}")


def fetch_results_page(
    params: LoginParams,
    take_screenshot: bool = False,
) -> FetchResult:
    """
    Función principal de este módulo.

    Flujo:
      - Abre el navegador con Playwright.
      - Va al login del ICFES.
      - Llena el formulario con los datos del estudiante.
      - Resuelve el CAPTCHA mediante Anti-Captcha (cuando implementes el stub).
      - Envía el formulario y espera los resultados.
      - Devuelve el HTML de la página de resultados y, opcionalmente, el pantallazo.
    """
    playwright = None
    browser = None
    context = None
    page: Optional[Page] = None
    screenshot_path: Optional[Path] = None

    try:
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(
            headless=HEADLESS,
            args=['--no-sandbox', '--disable-dev-shm-usage'],
        )
        context = browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/91.0.4472.124 Safari/537.36'
            ),
        )
        page = context.new_page()

        # Ir a la página de login
        print("Navegando a la página de login...")
        page.goto(ICFES_LOGIN_URL, wait_until="networkidle")
        time.sleep(2)

        # Llenar formulario
        print("Llenando formulario...")
        _fill_login_form(page, params)

        # Resolver CAPTCHA (cuando completes la integración)
        print("Resolviendo CAPTCHA (stub)...")
        _solve_captcha_with_anticaptcha(page)

        # Enviar formulario y esperar resultados
        print("Enviando formulario...")
        _submit_form_and_wait_results(page)

        # Manejar posibles errores en pantalla
        _handle_possible_errors(page)

        # (Opcional) tomar pantallazo
        if take_screenshot:
            print("Tomando screenshot...")
            screenshot_path = _take_results_screenshot(page, params.numero_documento)

        # Obtener HTML final
        html = page.content()
        print("Proceso completado exitosamente")

        return FetchResult(html=html, screenshot_path=screenshot_path)

    except Exception as e:
        # Tomar screenshot de error si ocurre
        if take_screenshot and page is not None:
            error_screenshot_path = SCREENSHOT_DIR / (
                f"error_{params.numero_documento}_"
                f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            )
            try:
                page.screenshot(path=str(error_screenshot_path), full_page=True)
                screenshot_path = error_screenshot_path
            except Exception as ss_e:
                print(f"No se pudo tomar screenshot de error: {ss_e}")

        print(f"Error durante la automatización: {e}")
        raise

    finally:
        # Cerrar recursos ordenadamente
        if context is not None:
            context.close()
        if browser is not None:
            browser.close()
        if playwright is not None:
            playwright.stop()

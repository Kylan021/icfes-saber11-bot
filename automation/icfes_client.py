from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
import time
from anticaptchaofficial.recaptchav2proxyless import recaptchaV2Proxyless

from playwright.sync_api import sync_playwright, Page

from config import ICFES_LOGIN_URL, HEADLESS, SCREENSHOT_DIR, ANTI_CAPTCHA_KEY

TIPO_DOC_LABEL_MAP = {
    "CC": "Cédula de ciudadanía",
    "TI": "Tarjeta de identidad",
    "CE": "Cédula de extranjería",
    "RC": "Registro civil",
    "PA": "Pasaporte",
}

@dataclass
class LoginParams:
    tipo_documento: str
    numero_documento: str
    fecha_nacimiento: str = ""
    numero_registro: str = ""

@dataclass
class FetchResult:
    html: str
    screenshot_path: Optional[Path] = None


def _normalizar_fecha(fecha_str: str) -> str:

    fecha_str = str(fecha_str).strip()
    if not fecha_str:
        return ""

    solo_fecha = fecha_str.split()[0]

    if "-" in solo_fecha and len(solo_fecha) == 10:
        return solo_fecha

    try:
        from datetime import datetime as _dt
        dt = _dt.strptime(solo_fecha, "%d/%m/%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:

        return solo_fecha



def _seleccionar_tipo_documento(page: Page, tipo_documento: str) -> None:
    code = (tipo_documento or "").strip()
    label = TIPO_DOC_LABEL_MAP.get(code.upper(), code)
    try:
        container_selector = (
            "icfes-selector-reactivo[formcontrolname='tipoIdentificacion'] "
            ".ng-select-container"
        )
        container = page.locator(container_selector)
        if container.count() == 0:
            print("No se encontró el combo de tipo de documento.")
            return
        container.first.click()
        page.wait_for_selector(".ng-dropdown-panel .ng-option", timeout=5000)
        option = page.locator(".ng-dropdown-panel .ng-option", has_text=label)
        if option.count() > 0:
            option.first.click()
        else:
            print(
                f"No se encontró una opción que contenga el texto '{label}'. "
                "Se seleccionará la primera opción disponible."
            )
            page.locator(".ng-dropdown-panel .ng-option").first.click()
        time.sleep(0.3)
    except Exception as e:
        print(f"Advertencia al seleccionar tipo de documento: {e}")


def _click_recaptcha_checkbox(page: Page) -> None:
    print("Haciendo clic en el checkbox del reCAPTCHA...")
    checkbox_iframe = page.locator("iframe[title='reCAPTCHA']").first
    if checkbox_iframe.count() > 0:
        checkbox_iframe.click()
        print("✔ Checkbox clickeado.")
        time.sleep(1)
    else:
        print("⚠ No se encontró el iframe del checkbox.")


def _handle_recaptcha_challenge(page: Page) -> None:
    print("Verificando si apareció desafío visual...")

    time.sleep(2)

    verify_btn = page.locator("button:has-text('Verificar'), button:has-text('Confirmar'), button:has-text('Next')")
    skip_btn = page.locator("button:has-text('Omitir'), button:has-text('Skip')")

    if verify_btn.count() > 0 and verify_btn.first.is_visible():
        print("✔ Desafío detectado. Haciendo clic en 'Verificar'...")
        verify_btn.first.click()
        time.sleep(3)
        _handle_recaptcha_challenge(page)
    elif skip_btn.count() > 0 and skip_btn.first.is_visible():
        print("✔ Desafío detectado. Haciendo clic en 'Omitir'...")
        skip_btn.first.click()
        time.sleep(3)
    else:
        print("✔ No apareció desafío visual.")

    challenge_frame = page.locator("iframe[src*='recaptcha/api2/bframe']")
    if challenge_frame.count() > 0 and challenge_frame.first.is_visible():
        print("⚠ El desafío sigue visible. Reintentando...")
        time.sleep(2)
        _handle_recaptcha_challenge(page)
    else:
        print("✔ Desafío cerrado.")


def _trigger_recaptcha_callback(page: Page) -> None:
    print("Ejecutando callback de éxito del CAPTCHA...")
    page.evaluate("""
        () => {
            const widget = document.querySelector('.g-recaptcha');
            const isInvisible = widget && widget.getAttribute('data-size') === 'invisible';
            if (isInvisible) {
                const widgetId = grecaptcha.getResponse ? 0 : null;
                if (widgetId !== null && typeof grecaptcha.execute === 'function') {
                    grecaptcha.execute(widgetId);
                }
            }
            const callbackName = widget?.getAttribute('data-callback');
            if (callbackName && typeof window[callbackName] === 'function') {
                const token = grecaptcha.getResponse();
                if (token) window[callbackName](token);
            }
            window.dispatchEvent(new CustomEvent('recaptcha-success', { detail: { success: true } }));
        }
    """)
    print("✔ Callback ejecutado (si aplica).")
    time.sleep(1)


def _solve_captcha_with_anticaptcha(page: Page) -> None:
    token = page.evaluate("() => grecaptcha.getResponse()")
    if token:
        print("✔ CAPTCHA ya resuelto anteriormente.")
        return

    print("Buscando reCAPTCHA en la página...")
    iframes = page.locator("iframe[src*='recaptcha']")
    if iframes.count() == 0:
        raise RuntimeError("No se detectó reCAPTCHA.")

    iframe = iframes.first
    sitekey = iframe.evaluate("""(el) => {
        const src = el.getAttribute('src');
        const match = src.match(/[?&]k=([^&]+)/);
        return match ? match[1] : null;
    }""")

    if not sitekey:
        raise RuntimeError("No se pudo extraer el sitekey.")

    print(f"✓ Sitekey detectado: {sitekey}")
    solver = recaptchaV2Proxyless()
    solver.set_verbose(1)
    solver.set_key(ANTI_CAPTCHA_KEY)
    solver.set_website_url(page.url)
    solver.set_website_key(sitekey)

    g_response = solver.solve_and_return_solution()
    if g_response == 0:
        raise RuntimeError(f"Error Anti-Captcha: {solver.error_code}")

    print("✓ CAPTCHA resuelto por Anti-Captcha.")
    print(f"Token (primeros 50 chars): {g_response[:50]}...")

    page.evaluate("""
        (token) => {
            const responseField = document.getElementById('g-recaptcha-response') ||
                                  document.querySelector('[name="g-recaptcha-response"]');
            if (responseField) {
                responseField.value = token;
                responseField.innerHTML = token;
                ['input', 'change'].forEach(evt => {
                    responseField.dispatchEvent(new Event(evt, { bubbles: true }));
                });
            }
        }
    """, g_response)

    _click_recaptcha_checkbox(page)
    _trigger_recaptcha_callback(page)
    _handle_recaptcha_challenge(page)

    print("Verificando si el CAPTCHA fue aceptado por el sitio...")
    page.wait_for_function("""
        () => {
            const tokenField = document.getElementById('g-recaptcha-response');
            return tokenField && tokenField.value.length > 0;
        }
    """, timeout=10000)
    print("✔ CAPTCHA aceptado por el sitio.")

    result = page.evaluate("""
        () => {
            const responseField = document.getElementById('g-recaptcha-response');
            return {
                hasValue: responseField && responseField.value.length > 0,
                buttonEnabled: !document.querySelector('button[type=\"submit\"]').disabled
            };
        }
    """)
    print(f"Verificación final: {result}")
    if not result["buttonEnabled"]:
        print("⚠ El botón de ingreso aún está deshabilitado.")


def _fill_login_form(page: Page, params: LoginParams) -> None:
    print("Llenando formulario...")
    page.wait_for_selector("form", timeout=10000)
    time.sleep(1)

    print("  → Seleccionando tipo de documento...")
    _seleccionar_tipo_documento(page, params.tipo_documento)
    time.sleep(0.5)

    print("  → Ingresando número de documento...")
    page.click("#identificacion")
    time.sleep(0.2)
    page.fill("#identificacion", params.numero_documento)
    time.sleep(0.3)
    page.evaluate("""
        () => {
            const input = document.getElementById('identificacion');
            if (input) {
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
                input.dispatchEvent(new Event('blur', { bubbles: true }));
            }
        }
    """)
    time.sleep(0.5)

    if params.fecha_nacimiento:
        print("  → Ingresando fecha de nacimiento...")
        fecha_normalizada = _normalizar_fecha(params.fecha_nacimiento)
        if fecha_normalizada:
            page.click("#fechaNacimiento")
            time.sleep(0.2)
            page.fill("#fechaNacimiento", fecha_normalizada)
            time.sleep(0.3)
            page.evaluate("""
                () => {
                    const input = document.getElementById('fechaNacimiento');
                    if (input) {
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                        input.dispatchEvent(new Event('blur', { bubbles: true }));
                    }
                }
            """)
            time.sleep(0.5)

    if params.numero_registro:
        print("  → Ingresando número de registro...")
        page.click("#numeroRegistro")
        time.sleep(0.2)
        page.fill("#numeroRegistro", params.numero_registro.upper())
        time.sleep(0.3)
        page.evaluate("""
            () => {
                const input = document.getElementById('numeroRegistro');
                if (input) {
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                    input.dispatchEvent(new Event('blur', { bubbles: true }));
                }
            }
        """)
        time.sleep(0.5)

    if not params.fecha_nacimiento and not params.numero_registro:
        print("ADVERTENCIA: No se proporcionó fecha de nacimiento ni número de registro")

    print("  → Verificando validaciones...")
    time.sleep(1)
    validation_errors = page.evaluate("""
        () => {
            const errors = [];
            const errorSelectors = [
                '.error-message',
                '.field-error',
                '.invalid-feedback',
                '.text-danger',
                'icfes-mensajes-formulario'
            ];
            errorSelectors.forEach(selector => {
                document.querySelectorAll(selector).forEach(el => {
                    if (el.offsetParent !== null && el.textContent.trim()) {
                        errors.push(el.textContent.trim());
                    }
                });
            });
            return errors;
        }
    """)
    if validation_errors:
        print(f"Errores: {validation_errors}")
    else:
        print("  ✓ Sin errores de validación")
    print("Formulario completado")


def _submit_form_and_wait_results(page: Page) -> None:
    print("Enviando formulario...")

    def _get_doc_for_filename() -> str:
        try:
            return page.evaluate("""
                () => {
                    const el = document.querySelector('#identificacion');
                    return el && el.value ? el.value.trim() : 'sin_identificacion';
                }
            """)
        except Exception:
            return "sin_identificacion"

    doc_val_before = _get_doc_for_filename()
    pre_send_html_path = SCREENSHOT_DIR / f"pre_send_{doc_val_before}.html"
    pre_send_html_path.write_text(page.content(), encoding="utf-8")
    print(f"HTML antes de enviar guardado en: {pre_send_html_path}")

    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle")
    time.sleep(5)

    doc_val_after = _get_doc_for_filename()
    post_send_html_path = SCREENSHOT_DIR / f"post_send_{doc_val_after}.html"
    post_send_html_path.write_text(page.content(), encoding="utf-8")
    print(f"HTML después de enviar guardado en: {post_send_html_path}")

    error_selectors = [
        ".error-message",
        ".alert-danger",
        ".text-danger",
        "[class*='error']",
        "[class*='alert']",
    ]
    for selector in error_selectors:
        loc = page.locator(selector)
        if loc.count() > 0 and loc.first.is_visible():
            error_text = (loc.first.text_content() or "").strip()
            raise RuntimeError(f"El sitio del ICFES muestra error: {error_text}")

    try:
        print("Esperando que cargue el puntaje general (máx. 30 s)...")
        page.wait_for_function("""
            () => {
                const el = document.querySelector("icfes-puntaje-general span");
                return el && el.textContent && /\\d+/.test(el.textContent);
            }
        """, timeout=30000)
        print("✔ Puntaje general cargado.")
    except Exception as e:
        print(f"⚠ No apareció el puntaje general: {e}")
        debug_html = SCREENSHOT_DIR / "debug_no_puntaje.html"
        debug_html.write_text(page.content(), encoding="utf-8")
        print(f"HTML guardado en: {debug_html}")

    try:
        print("Esperando que cargue el nombre del estudiante (máx. 10 s)...")
        page.wait_for_function("""
            () => {
                const el = document.querySelector("icfes-navbar button");
                return el && el.textContent && el.textContent.trim().length > 0;
            }
        """, timeout=10000)
        print("✔ Nombre cargado.")
    except Exception as e:
        print(f"⚠ No apareció el nombre: {e}")

    print(f"URL actual: {page.url}")
    if "resultados" not in page.url and "reporte" not in page.url:
        raise RuntimeError(
            "No llegamos a la página de resultados. "
            "La URL no contiene 'resultados' ni 'reporte'."
        )

    print("✔ Página de resultados cargada completamente.")


def _take_results_screenshot(page: Page, numero_documento: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{numero_documento}_{timestamp}.png"
    path = SCREENSHOT_DIR / filename
    page.screenshot(path=str(path), full_page=True)
    return path


def fetch_results_page(
    params: LoginParams,
    take_screenshot: bool = False,
) -> FetchResult:
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

        print("Navegando a la página de login...")
        page.goto(ICFES_LOGIN_URL, wait_until="networkidle")
        time.sleep(2)

        print("Llenando formulario...")
        _fill_login_form(page, params)

        print("Resolviendo CAPTCHA...")
        _solve_captcha_with_anticaptcha(page)

        print("Enviando formulario...")
        _submit_form_and_wait_results(page)

        real_html_path = SCREENSHOT_DIR / f"real_{params.numero_documento}_con_datos.html"
        real_html_path.write_text(page.content(), encoding="utf-8")
        print(f"HTML con datos guardado en: {real_html_path}")

        if take_screenshot:
            print("Tomando screenshot...")
            screenshot_path = _take_results_screenshot(page, params.numero_documento)

        html = page.content()
        print("✔ Proceso completado exitosamente")
        return FetchResult(html=html, screenshot_path=screenshot_path)

    except Exception as e:
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
        if context is not None:
            context.close()
        if browser is not None:
            browser.close()
        if playwright is not None:
            playwright.stop()
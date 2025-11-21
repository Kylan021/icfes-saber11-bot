from __future__ import annotations

from pathlib import Path

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    send_from_directory,
    flash,
)

from werkzeug.utils import secure_filename

from config import Config, DATA_DIR, EXPORT_DIR, SCREENSHOT_DIR
from services.results_service import (
    consultar_un_estudiante,
    consultar_y_exportar_desde_excel,
)

app = Flask(__name__)
app.config.from_object(Config)

# Carpeta para subir archivos de Excel
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB máximo (por si acaso)


@app.route("/", methods=["GET"])
def index():
    """
    Página inicial con formulario de consulta manual:
      - tipo_documento
      - numero_documento
      - fecha_nacimiento
      - checkbox: tomar screenshot
    """
    return render_template("index.html")


@app.route("/consulta-manual", methods=["POST"])
def consulta_manual():
    """
    Procesa la consulta de un solo estudiante a partir
    del formulario de la página principal.
    """
    tipo_doc = request.form.get("tipo_documento", "").strip()
    numero_doc = request.form.get("numero_documento", "").strip()
    fecha_nac = request.form.get("fecha_nacimiento", "").strip()
    take_screenshot = bool(request.form.get("take_screenshot"))

    if not tipo_doc or not numero_doc or not fecha_nac:
        flash("Por favor completa todos los campos.", "danger")
        return redirect(url_for("index"))

    # Llamar al servicio de consulta
    resultado = consultar_un_estudiante(
        tipo_documento=tipo_doc,
        numero_documento=numero_doc,
        fecha_nacimiento=fecha_nac,
        take_screenshot=take_screenshot,
    )

    # Renderizar una plantilla de resultados
    # La plantilla debe mostrar:
    # - Datos básicos
    # - Puntaje general y percentil general
    # - Puntajes y percentiles por prueba
    # - Mensaje de error (si 'error' != None)
    # - Screenshot (si existe ruta)
    return render_template("resultados.html", resultado=resultado)


@app.route("/consulta-excel", methods=["GET"])
def consulta_excel_form():
    """
    Muestra un formulario para subir un archivo Excel con las columnas:
      - tipo_documento
      - numero_documento
      - fecha_nacimiento
    """
    return render_template("consulta_excel.html")


@app.route("/consulta-excel", methods=["POST"])
def consulta_excel_procesar():
    """
    Procesa el archivo Excel subido, consulta todos los estudiantes
    y genera los archivos de salida (CSV, Excel, JSON).
    """
    file = request.files.get("archivo")
    take_screenshot = bool(request.form.get("take_screenshot"))

    if not file or file.filename == "":
        flash("Debes seleccionar un archivo Excel.", "danger")
        return redirect(url_for("consulta_excel_form"))

    # Validar extensión mínima (simplemente por seguridad básica)
    filename = secure_filename(file.filename)
    if not (filename.endswith(".xls") or filename.endswith(".xlsx")):
        flash("El archivo debe ser un Excel (.xls o .xlsx).", "danger")
        return redirect(url_for("consulta_excel_form"))

    # Guardar archivo subido
    upload_path = UPLOAD_DIR / filename
    file.save(str(upload_path))

    # Consultar y exportar resultados
    df_resultados, rutas = consultar_y_exportar_desde_excel(
        excel_path=upload_path,
        take_screenshot=take_screenshot,
        base_filename="resultados_icfes",  # puedes personalizarlo si quieres
    )

    # Mostrar una página con:
    # - Resumen de cuántos registros
    # - Cuántos errores hubo
    # - Links de descarga para CSV / Excel / JSON
    num_registros = len(df_resultados)
    num_errores = df_resultados["error"].notna().sum() if "error" in df_resultados.columns else 0

    return render_template(
        "resultados_excel.html",
        num_registros=num_registros,
        num_errores=num_errores,
        rutas=rutas,
    )


@app.route("/descargar/<formato>")
def descargar_resultados(formato: str):
    """
    Permite descargar los archivos generados en EXPORT_DIR.

    Soporta 'csv', 'xlsx', 'json' usando el nombre base:
      resultados_icfes.<ext>
    """
    formato = formato.lower()
    if formato not in ("csv", "xlsx", "json"):
        flash("Formato no soportado.", "danger")
        return redirect(url_for("consulta_excel_form"))

    filename = f"resultados_icfes.{formato}"
    file_path = EXPORT_DIR / filename

    if not file_path.exists():
        flash("Aún no se ha generado el archivo solicitado.", "warning")
        return redirect(url_for("consulta_excel_form"))

    return send_from_directory(
        directory=str(EXPORT_DIR),
        path=file_path.name,
        as_attachment=True,
    )


@app.route("/screenshots/<path:filename>")
def ver_screenshot(filename: str):
    """
    Sirve archivos de screenshot desde SCREENSHOT_DIR.
    Esto permite mostrar o descargar capturas de resultados.
    """
    file_path = SCREENSHOT_DIR / filename
    if not file_path.exists():
        flash("La captura de pantalla no existe.", "warning")
        return redirect(url_for("index"))

    return send_from_directory(
        directory=str(SCREENSHOT_DIR),
        path=file_path.name,
        as_attachment=False,  # False = se muestra en el navegador
    )


if __name__ == "__main__":
    # Debug=True sólo para desarrollo local
    app.run(host="0.0.0.0", port=5000, debug=True)

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
from pathlib import Path

from config import Config, DATA_DIR, EXPORT_DIR, SCREENSHOT_DIR
from services.results_service import (
    consultar_un_estudiante,
    consultar_y_exportar_desde_excel,
)

app = Flask(__name__)
app.config.from_object(Config)

# IMPORTANTE: Configurar secret key para flash messages
app.secret_key = app.config['SECRET_KEY']

# Carpeta para subir archivos
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB


@app.route("/", methods=["GET"])
def index():
    """Página inicial con formulario de consulta manual"""
    return render_template("index.html")


@app.route("/consulta-manual", methods=["POST"])
def consulta_manual():
    """Procesa la consulta de un solo estudiante"""
    tipo_doc = request.form.get("tipo_documento", "").strip()
    numero_doc = request.form.get("numero_documento", "").strip()
    fecha_nac = request.form.get("fecha_nacimiento", "").strip()
    numero_reg = request.form.get("numero_registro", "").strip()
    take_screenshot = bool(request.form.get("take_screenshot"))

    if not tipo_doc or not numero_doc:
        flash("Tipo y número de documento son obligatorios.", "danger")
        return redirect(url_for("index"))
    
    if not fecha_nac and not numero_reg:
        flash("Debes proporcionar fecha de nacimiento O número de registro.", "danger")
        return redirect(url_for("index"))

    try:
        resultado = consultar_un_estudiante(
            tipo_documento=tipo_doc,
            numero_documento=numero_doc,
            fecha_nacimiento=fecha_nac,
            numero_registro=numero_reg,
            take_screenshot=take_screenshot,
        )
        
        if resultado.get("error"):
            flash(f"Error en la consulta: {resultado['error']}", "warning")
        
        return render_template("resultados.html", resultado=resultado)
        
    except Exception as e:
        flash(f"Error inesperado: {str(e)}", "danger")
        return redirect(url_for("index"))


@app.route("/consulta-excel", methods=["GET"])
def consulta_excel_form():
    """Muestra formulario para subir Excel"""
    return render_template("consulta_excel.html")


@app.route("/consulta-excel", methods=["POST"])
def consulta_excel_procesar():
    """Procesa archivo Excel"""
    file = request.files.get("archivo")
    take_screenshot = bool(request.form.get("take_screenshot"))

    if not file or file.filename == "":
        flash("Debes seleccionar un archivo Excel.", "danger")
        return redirect(url_for("consulta_excel_form"))

    filename = secure_filename(file.filename)
    if not (filename.endswith(".xls") or filename.endswith(".xlsx")):
        flash("El archivo debe ser un Excel (.xls o .xlsx).", "danger")
        return redirect(url_for("consulta_excel_form"))

    # Guardar archivo
    upload_path = UPLOAD_DIR / filename
    file.save(str(upload_path))

    try:
        # Procesar Excel
        df_resultados, rutas = consultar_y_exportar_desde_excel(
            excel_path=upload_path,
            take_screenshot=take_screenshot,
            base_filename="resultados_icfes",
        )

        num_registros = len(df_resultados)
        num_errores = df_resultados["error"].notna().sum() if "error" in df_resultados.columns else 0

        flash(f"Proceso completado: {num_registros} registros procesados", "success")
        
        return render_template(
            "resultados_excel.html",
            num_registros=num_registros,
            num_errores=num_errores,
            rutas=rutas,
        )
        
    except Exception as e:
        flash(f"Error al procesar archivo: {str(e)}", "danger")
        return redirect(url_for("consulta_excel_form"))


@app.route("/descargar/<formato>")
def descargar_resultados(formato: str):
    """Descarga archivos generados"""
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
    """Sirve archivos de screenshot"""
    file_path = SCREENSHOT_DIR / filename
    if not file_path.exists():
        flash("La captura de pantalla no existe.", "warning")
        return redirect(url_for("index"))

    return send_from_directory(
        directory=str(SCREENSHOT_DIR),
        path=file_path.name,
        as_attachment=False,
    )


if __name__ == "__main__":
    print("Iniciando servidor Flask...")
    print(f"Directorio de exportación: {EXPORT_DIR}")
    print(f"Directorio de screenshots: {SCREENSHOT_DIR}")
    app.run(host="0.0.0.0", port=5000, debug=True)
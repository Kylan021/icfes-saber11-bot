from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from config import EXPORT_DIR
from automation.icfes_client import LoginParams, fetch_results_page
from scraping.icfes_parser import parse_all


def consultar_un_estudiante(
    tipo_documento: str,
    numero_documento: str,
    fecha_nacimiento: str,
    take_screenshot: bool = False,
) -> Dict:
    """
    Consulta los resultados de un solo estudiante y devuelve
    un diccionario con todos los datos parseados + metadatos.

    Estructura típica del resultado:
    {
        "tipo_documento": "...",
        "numero_documento": "...",
        "fecha_nacimiento": "...",
        "nombre_estudiante": "...",
        "puntaje_general": 312,
        "percentil_general": 92,
        "puntaje_lectura_critica": 58,
        "percentil_lectura_critica": 85,
        ...
        "screenshot_path": "exports/...png" (opcional),
        "error": None o mensaje de error
    }
    """
    params = LoginParams(
        tipo_documento=tipo_documento,
        numero_documento=numero_documento,
        fecha_nacimiento=fecha_nacimiento,
    )

    try:
        # 1. Obtener HTML (y screenshot opcional) usando Playwright
        fetch_result = fetch_results_page(params, take_screenshot=take_screenshot)

        # 2. Parsear HTML a dict de resultados
        parsed = parse_all(fetch_result.html)

        # 3. Construir dict final
        result: Dict = {
            "tipo_documento": tipo_documento,
            "numero_documento": numero_documento,
            "fecha_nacimiento": fecha_nacimiento,
            "screenshot_path": str(fetch_result.screenshot_path) if fetch_result.screenshot_path else None,
            "error": None,
        }

        # Mezclar con los datos parseados (nombre, puntajes, etc.)
        result.update(parsed)

        return result

    except Exception as e:
        # En caso de error, devolvemos un diccionario con el mensaje
        return {
            "tipo_documento": tipo_documento,
            "numero_documento": numero_documento,
            "fecha_nacimiento": fecha_nacimiento,
            "screenshot_path": None,
            "error": str(e),
        }


def consultar_desde_excel(
    excel_path: str | Path,
    take_screenshot: bool = False,
    sheet_name: str | int | None = 0,
) -> pd.DataFrame:
    """
    Lee un archivo Excel con las columnas:
      - tipo_documento
      - numero_documento
      - fecha_nacimiento

    Consulta los resultados de cada fila y devuelve un DataFrame
    con una fila por estudiante y todas las columnas parseadas.

    Si ocurre un error con algún estudiante, se registra en la
    columna 'error' y se continúa con los demás.
    """
    excel_path = Path(excel_path)
    df_input = pd.read_excel(excel_path, sheet_name=sheet_name)

    resultados: List[Dict] = []

    for idx, row in df_input.iterrows():
        tipo_doc = str(row.get("tipo_documento", "")).strip()
        num_doc = str(row.get("numero_documento", "")).strip()
        fecha_nac = str(row.get("fecha_nacimiento", "")).strip()

        if not tipo_doc or not num_doc or not fecha_nac:
            resultados.append(
                {
                    "tipo_documento": tipo_doc,
                    "numero_documento": num_doc,
                    "fecha_nacimiento": fecha_nac,
                    "screenshot_path": None,
                    "error": "Datos incompletos en la fila de entrada",
                }
            )
            continue

        print(f"Consultando estudiante {idx + 1}: {tipo_doc} - {num_doc} ...")
        result = consultar_un_estudiante(
            tipo_documento=tipo_doc,
            numero_documento=num_doc,
            fecha_nacimiento=fecha_nac,
            take_screenshot=take_screenshot,
        )
        resultados.append(result)

    df_resultados = pd.DataFrame(resultados)
    return df_resultados


def exportar_resultados(
    df: pd.DataFrame,
    base_filename: str = "resultados_icfes",
) -> Dict[str, Path]:
    """
    Exporta el DataFrame de resultados a CSV, Excel y JSON
    en la carpeta EXPORT_DIR, usando base_filename como prefijo.

    Devuelve un dict con las rutas generadas:
    {
        "csv": Path(...),
        "xlsx": Path(...),
        "json": Path(...),
    }
    """
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    csv_path = EXPORT_DIR / f"{base_filename}.csv"
    xlsx_path = EXPORT_DIR / f"{base_filename}.xlsx"
    json_path = EXPORT_DIR / f"{base_filename}.json"

    # CSV
    df.to_csv(csv_path, index=False)

    # Excel
    df.to_excel(xlsx_path, index=False)

    # JSON (lista de registros)
    df.to_json(json_path, orient="records", force_ascii=False)

    return {
        "csv": csv_path,
        "xlsx": xlsx_path,
        "json": json_path,
    }


def consultar_y_exportar_desde_excel(
    excel_path: str | Path,
    take_screenshot: bool = False,
    base_filename: str = "resultados_icfes",
) -> Tuple[pd.DataFrame, Dict[str, Path]]:
    """
    Flujo completo:
      1. Lee un Excel de entrada.
      2. Consulta los resultados en el portal.
      3. Devuelve el DataFrame resultante.
      4. Exporta CSV, Excel y JSON.
      5. Devuelve también las rutas de exportación.

    Útil para integrarlo en el endpoint de Flask que maneje la carga de Excel.
    """
    df_resultados = consultar_desde_excel(
        excel_path=excel_path,
        take_screenshot=take_screenshot,
    )

    rutas = exportar_resultados(
        df=df_resultados,
        base_filename=base_filename,
    )

    return df_resultados, rutas

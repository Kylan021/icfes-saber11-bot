from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

from config import EXPORT_DIR
from automation.icfes_client import LoginParams, fetch_results_page
from scraping.icfes_parser import parse_all


def consultar_un_estudiante(
    tipo_documento: str,
    numero_documento: str,
    fecha_nacimiento: str = "",
    numero_registro: str = "",
    take_screenshot: bool = False,
) -> Dict:
    """
    Consulta los resultados de un solo estudiante.
    Ahora soporta número de registro opcional.
    """
    params = LoginParams(
        tipo_documento=tipo_documento,
        numero_documento=numero_documento,
        fecha_nacimiento=fecha_nacimiento,
        numero_registro=numero_registro,
    )

    try:
        print(f"🔍 Consultando: {tipo_documento} {numero_documento}")
        fetch_result = fetch_results_page(params, take_screenshot=take_screenshot)

        parsed = parse_all(fetch_result.html)

        result: Dict = {
            "tipo_documento": tipo_documento,
            "numero_documento": numero_documento,
            "fecha_nacimiento": fecha_nacimiento,
            "numero_registro": numero_registro,
            "screenshot_path": str(fetch_result.screenshot_path) if fetch_result.screenshot_path else None,
            "error": None,
        }

        result.update(parsed)
        print(f"✅ Consulta exitosa: {parsed.get('nombre_estudiante', 'N/A')}")
        return result

    except Exception as e:
        print(f"❌ Error en consulta: {str(e)}")
        return {
            "tipo_documento": tipo_documento,
            "numero_documento": numero_documento,
            "fecha_nacimiento": fecha_nacimiento,
            "numero_registro": numero_registro,
            "screenshot_path": None,
            "nombre_estudiante": None,
            "puntaje_general": None,
            "percentil_general": None,
            "error": str(e),
        }


def consultar_desde_excel(
    excel_path: str | Path,
    take_screenshot: bool = False,
    sheet_name: str | int | None = 0,
) -> pd.DataFrame:
    """
    Lee un archivo Excel y consulta los resultados de cada estudiante.
    """
    excel_path = Path(excel_path)
    
    if not excel_path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {excel_path}")
    
    print(f"📂 Leyendo Excel: {excel_path}")
    df_input = pd.read_excel(excel_path, sheet_name=sheet_name)
    
    print(f"📊 Total de registros: {len(df_input)}")

    resultados: List[Dict] = []

    for idx, row in df_input.iterrows():
        tipo_doc = str(row.get("tipo_documento", "")).strip()
        num_doc = str(row.get("numero_documento", "")).strip()
        fecha_nac = str(row.get("fecha_nacimiento", "")).strip()

        if not tipo_doc or not num_doc or not fecha_nac:
            print(f"⚠️  Fila {idx + 1}: Datos incompletos")
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

        print(f"\n🔄 [{idx + 1}/{len(df_input)}] Procesando: {tipo_doc} - {num_doc}")
        
        result = consultar_un_estudiante(
            tipo_documento=tipo_doc,
            numero_documento=num_doc,
            fecha_nacimiento=fecha_nac,
            take_screenshot=take_screenshot,
        )
        resultados.append(result)

    df_resultados = pd.DataFrame(resultados)
    print(f"\n✅ Proceso completado: {len(df_resultados)} registros procesados")
    
    return df_resultados


def exportar_resultados(
    df: pd.DataFrame,
    base_filename: str = "resultados_icfes",
) -> Dict[str, Path]:
    """
    Exporta el DataFrame de resultados a CSV, Excel y JSON.
    """
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    csv_path = EXPORT_DIR / f"{base_filename}.csv"
    xlsx_path = EXPORT_DIR / f"{base_filename}.xlsx"
    json_path = EXPORT_DIR / f"{base_filename}.json"

    print(f" Exportando resultados...")
    
    # CSV
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f"  ✓ CSV: {csv_path}")

    # Excel
    with pd.ExcelWriter(xlsx_path, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Resultados')
    print(f"  ✓ Excel: {xlsx_path}")

    # JSON
    df.to_json(json_path, orient="records", force_ascii=False, indent=2)
    print(f"  ✓ JSON: {json_path}")

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
    Flujo completo: Lee Excel → Consulta → Exporta
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
# ICFES Saber 11 — Bot de Consulta Automática

Automatización de consultas a la plataforma oficial del ICFES Saber 11, con soporte para:

- Consulta manual  
- Consulta masiva por archivo Excel  
- Resolución automática del CAPTCHA  
- Capturas de pantalla por estudiante  
- Exportación de resultados (CSV, Excel, JSON)  
- Scraping estructurado del reporte oficial (puntajes, percentiles, datos del estudiante)

Proyecto desarrollado en **Python + Playwright + Flask**, con procesamiento de datos en **pandas**.

---

## Estructura del Proyecto

```
icfes-saber11-bot/
├─ app.py                  # App Flask (punto de entrada)
├─ config.py               # Configuración general (keys, rutas, flags)
├─ requirements.txt        # Dependencias (Flask, Playwright, pandas, etc.)
│
├─ automation/
│  ├─ __init__.py
│  └─ icfes_client.py      # Lógica con Playwright + AntiCaptcha + screenshots
│
├─ scraping/
│  ├─ __init__.py
│  └─ icfes_parser.py      # Funciones para extraer datos del HTML de resultados
│
├─ services/
│  ├─ __init__.py
│  └─ results_service.py   # Orquesta: llama a automation + scraping + pandas
│
├─ templates/
│  ├─ base.html            # Layout base
│  ├─ index.html           # Formulario consulta manual
│  ├─ consulta_excel.html  # Subir archivo Excel
│  └─ resultados.html      # Vista de resultados
│
├─ data/
│  └─ ejemplos/
│     └─ plantilla_entrada.xlsx  # Ejemplo de archivo Excel de entrada
│
├─ exports/
│  ├─ resultados_general.csv
│  ├─ resultados_general.xlsx
│  └─ resultados_general.json    # Archivos finales
│
└─ screenshots/
   └─ ...                        # Capturas por estudiante
```

---

## Instalación

### 1. Crear entorno virtual
```
python -m venv venv
source venv/bin/activate    # Linux/Mac
venv\Scripts\activate     # Windows
```

### 2. Instalar dependencias
```
pip install -r requirements.txt
```

### 3. Instalar Playwright
```
playwright install
```

---

## Ejecución

```
python app.py
```

Abrir en el navegador:

```
http://127.0.0.1:5000/
```

---

## Autores

- Andrés Torres  
- Sergio Angulo  
- Jorge Narváez  
- Jesús Payares  
- Juan Puello  

---

## Licencia

MIT License  
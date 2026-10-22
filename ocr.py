"""
OCR offline con Tesseract + validacion y extraccion de campos con regex.

Se ejecuta UNA SOLA VEZ y guarda el resultado en datos/documentos_ocr.json.
El webhook solo lee ese fichero: el OCR tarda segundos y Dialogflow corta a
los 5, asi que nunca puede ir dentro de una peticion.

Uso:
    python ocr.py
"""

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
import pytesseract
from PIL import Image, ImageOps

BASE = Path(__file__).parent
CARPETA = BASE / "documentos"
SALIDA = BASE / "datos" / "documentos_ocr.json"
TESSDATA = BASE / "tessdata"   # aqui esta spa.traineddata
EXTENSIONES = (".jpg", ".jpeg", ".png", ".tif", ".tiff")

# En Mac con Apple Silicon el tesseract de /usr/local puede ser x86 y no
# arrancar: preferimos el de Homebrew si existe.
for candidato in ("/opt/homebrew/bin/tesseract", shutil.which("tesseract")):
    if candidato and Path(candidato).is_file():
        pytesseract.pytesseract.tesseract_cmd = candidato
        break

# --psm 6 = "un bloque de texto uniforme": funciona bien con parrafos y tablas simples.
CONFIG_TESSERACT = f"--psm 6 --tessdata-dir {TESSDATA}"


# Regex de validacion / extraccion

PATRONES = {
    # Referencia de documento, p. ej. FZ-NOR-2026-01
    "referencia": r"\bFZ-[A-Z]{3}-\d{4}-\d{2}\b",
    # Fechas tipo 31/12/2026
    "fecha": r"\b\d{1,2}/\d{1,2}/\d{4}\b",
    # Importes tipo 29,90 € / 1.250,00 €
    "importe": r"\b\d{1,3}(?:\.\d{3})*,\d{2}\s?€",
    # Horas tipo 07:30
    "hora": r"\b(?:[01]\d|2[0-3]):[0-5]\d\b",
    # Telefono espanol de 9 digitos
    "telefono": r"\b[6-9]\d{2}\s?\d{3}\s?\d{3}\b",
}


def enderezar(imagen: Image.Image) -> Image.Image:
    """Prueba giros de -2 a 2 grados y se queda con el que deja las lineas de texto mas nitidas."""
    pequena = imagen.resize((imagen.width // 2, imagen.height // 2))
    mejor, mejor_puntuacion = 0.0, -1.0
    for angulo in np.arange(-2, 2.01, 0.2):
        tinta = np.asarray(pequena.rotate(angulo, fillcolor=255)) < 140
        puntuacion = np.var(tinta.sum(axis=1))
        if puntuacion > mejor_puntuacion:
            mejor, mejor_puntuacion = angulo, puntuacion
    return imagen.rotate(mejor, expand=False, fillcolor=255, resample=Image.BICUBIC)


def quitar_lineas(tinta: np.ndarray, largo: int) -> np.ndarray:
    """
    Borra de la imagen binaria (True = tinta) las rayas de mas de `largo` pixeles,
    horizontales y verticales. Son los bordes de las tablas: Tesseract los lee
    como letras sueltas ('|', '[') y desbarata el reconocimiento de las celdas.
    Las letras miden menos que `largo`, asi que no se tocan.
    """
    limpia = tinta.copy()
    for eje in (0, 1):
        vista = limpia if eje == 1 else limpia.T      # filas de la vista = lineas a revisar
        for i in range(vista.shape[0]):
            fila = np.concatenate(([0], vista[i].astype(np.int8), [0]))
            cambios = np.flatnonzero(np.diff(fila))
            for ini, fin in zip(cambios[::2], cambios[1::2]):
                if fin - ini > largo:
                    vista[i, ini:fin] = False
    return limpia


def leer_documento(ruta: Path) -> str:
    """
    Preprocesado, en este orden y por esto:
      1. escala de grises + autocontraste: el tono de papel y el ruido del escaneo
         suben el fondo.
      2. enderezar: el escaneo sale con unos grados de giro; sin esto las rayas
         de las tablas quedan inclinadas y no se pueden borrar.
      3. ampliar x2: Tesseract rinde mejor con letra de ~30 px de alto.
      4. binarizar y quitar rayas de tabla.
    """
    imagen = Image.open(ruta).convert("L")
    imagen = ImageOps.autocontrast(imagen, cutoff=2)
    imagen = enderezar(imagen)
    imagen = imagen.resize((imagen.width * 2, imagen.height * 2), Image.LANCZOS)
    tinta = quitar_lineas(np.asarray(imagen) < 160, largo=90)
    limpia = Image.fromarray(np.where(tinta, 0, 255).astype(np.uint8))
    return pytesseract.image_to_string(limpia, lang="spa", config=CONFIG_TESSERACT)


def fecha_valida(texto: str) -> bool:
    try:
        datetime.strptime(texto, "%d/%m/%Y")
        return True
    except ValueError:
        return False


def analizar(texto: str) -> dict:
    """Extrae campos con regex y valida el documento."""
    campos = {nombre: re.findall(patron, texto) for nombre, patron in PATRONES.items()}
    fechas_malas = [f for f in campos["fecha"] if not fecha_valida(f)]
    campos["valido"] = bool(campos["referencia"]) and not fechas_malas
    if not campos["referencia"]:
        campos["aviso"] = "No se ha leído la referencia del documento: revisar el OCR."
    elif fechas_malas:
        campos["aviso"] = f"Fechas no válidas: {fechas_malas}"
    return campos


def main() -> None:
    imagenes = sorted(p for p in CARPETA.iterdir() if p.suffix.lower() in EXTENSIONES)
    if not imagenes:
        raise SystemExit("No hay imágenes en documentos/. Ejecuta antes generar_documentos.py")

    resultado = {}
    for ruta in imagenes:
        texto = leer_documento(ruta).strip()
        campos = analizar(texto)
        resultado[ruta.name] = {"texto": texto, "campos": campos}
        estado = "OK" if campos["valido"] else "REVISAR"
        print(f"[{estado}] {ruta.name}: {len(texto)} caracteres, "
              f"ref={campos['referencia']}, {len(campos['importe'])} importes, "
              f"{len(campos['hora'])} horas")

    SALIDA.parent.mkdir(exist_ok=True)
    SALIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nGuardado en {SALIDA}")


if __name__ == "__main__":
    main()

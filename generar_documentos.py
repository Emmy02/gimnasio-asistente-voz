"""
Genera los 4 documentos (imagenes) de FitZone que luego lee el OCR.

Son documentos sinteticos: los dibujamos con Pillow y les aplicamos un giro
y un poco de ruido para que parezcan escaneados y el preprocesado del OCR
tenga algo que arreglar. El horario sale de negocio.py.

Uso (una sola vez):
    python generar_documentos.py
"""

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from negocio import CLASES, DIAS

CARPETA = Path(__file__).parent / "documentos"
FUENTE = "/System/Library/Fonts/Supplemental/Arial.ttf"
FUENTE_NEGRITA = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
ANCHO, ALTO = 1240, 1500
MARGEN = 80


def fuente(tam: int, negrita: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FUENTE_NEGRITA if negrita else FUENTE, tam)


def nueva_pagina(titulo: str, referencia: str):
    img = Image.new("L", (ANCHO, ALTO), 250)
    d = ImageDraw.Draw(img)
    d.text((MARGEN, 70), "FitZone Gimnasio", font=fuente(30), fill=90)
    d.text((MARGEN, 120), titulo, font=fuente(48, True), fill=20)
    d.text((MARGEN, 190), f"Ref. {referencia}", font=fuente(28), fill=60)
    d.line((MARGEN, 240, ANCHO - MARGEN, 240), fill=120, width=2)
    return img, d, 280


def escribir_lineas(d, y: int, lineas: list[str], tam: int = 32, salto: int = 52) -> int:
    for linea in lineas:
        d.text((MARGEN, y), linea, font=fuente(tam), fill=20)
        y += salto
    return y


def tabla(d, y: int, cabecera: list[str], filas: list[list[str]], anchos: list[int]) -> int:
    alto_fila = 56
    x0 = MARGEN
    todas = [cabecera] + filas
    for i, fila in enumerate(todas):
        x = x0
        for celda, ancho in zip(fila, anchos):
            d.rectangle((x, y, x + ancho, y + alto_fila), outline=90, width=2)
            d.text((x + 12, y + 12), celda, font=fuente(30, i == 0), fill=20)
            x += ancho
        y += alto_fila
    return y


def aspecto_escaneado(img: Image.Image) -> Image.Image:
    """Giro minimo, ruido y un punto de desenfoque."""
    random.seed(7)
    img = img.rotate(0.6, expand=False, fillcolor=250, resample=Image.BICUBIC)
    px = img.load()
    for _ in range(25000):
        x, y = random.randrange(img.width), random.randrange(img.height)
        px[x, y] = max(0, px[x, y] - random.randint(20, 90))
    return img.filter(ImageFilter.GaussianBlur(0.6))


def guardar(img: Image.Image, nombre: str) -> None:
    aspecto_escaneado(img).save(CARPETA / nombre)
    print("  creado:", nombre)


def normativa():
    img, d, y = nueva_pagina("Normativa de uso de las instalaciones", "FZ-NOR-2026-01")
    escribir_lineas(d, y, [
        "Vigente desde el 01/09/2026.",
        "",
        "1. Es obligatorio usar toalla en la sala de máquinas.",
        "2. Se debe llevar calzado deportivo limpio de suela blanda.",
        "3. La edad mínima de acceso es de 16 años. Los menores de",
        "    18 años necesitan autorización firmada por su tutor.",
        "4. No se permite el acceso con mascotas.",
        "5. En la piscina es obligatorio el gorro de baño y la ducha previa.",
        "6. Las taquillas se vacían cada noche a las 23:00. El gimnasio",
        "    no se hace responsable de los objetos olvidados.",
        "7. Horario: lunes a viernes de 07:00 a 22:30, sábados de 09:00",
        "    a 20:00 y domingos y festivos de 09:00 a 14:00.",
        "",
        "Reservas de clases dirigidas",
        "- Se puede reservar con un máximo de 14 días de antelación.",
        "- Se puede cancelar hasta 2 horas antes de la clase.",
        "- Tres ausencias sin avisar en 30 días bloquean las reservas",
        "    durante 7 días.",
        "",
        "Reposición de tarjeta de acceso: 5,00 €.",
    ])
    guardar(img, "normativa_instalaciones.png")


def tarifas():
    img, d, y = nueva_pagina("Tarifas y planes de socio", "FZ-TAR-2026-02")
    y = escribir_lineas(d, y, ["Tarifas válidas hasta el 31/12/2026.", ""])
    y = tabla(d, y, ["Plan", "Cuota", "Incluye"], [
        ["Básico", "29,90 € al mes", "Sala de máquinas"],
        ["Plus", "39,90 € al mes", "Máquinas y clases dirigidas"],
        ["Premium", "49,90 € al mes", "Clases, piscina y sauna"],
    ], [220, 330, 530])
    escribir_lineas(d, y + 40, [
        "Matrícula: 25,00 € (gratuita durante el mes de septiembre).",
        "No hay permanencia mínima.",
        "Para darse de baja hay que avisar con 15 días de antelación.",
        "El plan Básico no incluye clases dirigidas.",
        "",
        "Atención al socio: 912 345 678",
    ])
    guardar(img, "tarifas_planes.png")


def horario_clases():
    img, d, y = nueva_pagina("Horario semanal de clases dirigidas", "FZ-HOR-2026-03")
    filas = []
    for dia in range(7):
        for clase, info in CLASES.items():
            for wd, hora in info["horario"]:
                if wd == dia:
                    filas.append([DIAS[dia].capitalize(), hora, clase.capitalize(),
                                  info["sala"], str(info["plazas"])])
    y = tabla(d, y, ["Día", "Hora", "Clase", "Sala", "Plazas"], filas,
              [230, 150, 250, 200, 150])
    escribir_lineas(d, y + 40, [
        "Clases incluidas en los planes Plus y Premium.",
        "Reserva con la app o llamando al 912 345 678.",
    ])
    guardar(img, "horario_clases.png")


def entrenamiento():
    img, d, y = nueva_pagina("Plan de entrenamiento de iniciación", "FZ-ENT-2026-04")
    y = escribir_lineas(d, y, [
        "Rutina de fuerza para principiantes: 3 días por semana.",
        "Descansa un día entre sesiones.", "",
    ])
    y = tabla(d, y, ["Día", "Ejercicio", "Series x reps", "Descanso"], [
        ["Lunes", "Sentadilla", "3 x 12", "90 s"],
        ["Lunes", "Prensa de piernas", "3 x 12", "90 s"],
        ["Miércoles", "Press de banca", "3 x 10", "90 s"],
        ["Miércoles", "Remo con mancuerna", "3 x 10", "90 s"],
        ["Viernes", "Peso muerto rumano", "3 x 10", "120 s"],
        ["Viernes", "Plancha", "3 x 30 s", "60 s"],
    ], [220, 440, 260, 180])
    escribir_lineas(d, y + 40, [
        "Calienta 10 minutos antes de empezar.",
        "Sube el peso solo cuando completes todas las repeticiones.",
    ])
    guardar(img, "plan_entrenamiento.png")


if __name__ == "__main__":
    CARPETA.mkdir(exist_ok=True)
    print("Generando documentos...")
    normativa()
    tarifas()
    horario_clases()
    entrenamiento()

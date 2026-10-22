"""
Datos de negocio simulados de FitZone.

Es la unica fuente de verdad: la usan generar_documentos.py (para dibujar el
horario) y main.py (para decidir las respuestas), asi que lo que dice el
documento y lo que hace el webhook nunca se contradicen.

En un sistema real esto seria una base de datos.
"""

# weekday(): 0 = lunes ... 6 = domingo
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

CLASES = {
    "yoga":     {"sala": "Sala 1", "plazas": 15, "horario": [(0, "19:00"), (2, "19:00"), (5, "10:00")]},
    "pilates":  {"sala": "Sala 1", "plazas": 15, "horario": [(1, "18:00"), (3, "18:00")]},
    "spinning": {"sala": "Sala 2", "plazas": 20, "horario": [(0, "07:30"), (2, "07:30"), (4, "07:30")]},
    "crossfit": {"sala": "Box",    "plazas": 12, "horario": [(1, "20:00"), (3, "20:00")]},
    "zumba":    {"sala": "Sala 2", "plazas": 25, "horario": [(2, "18:30"), (4, "18:30")]},
    "boxeo":    {"sala": "Box",    "plazas": 12, "horario": [(0, "20:30"), (3, "20:30")]},
}

# Sesiones sin plazas (clase, weekday, hora)
SESIONES_COMPLETAS = {("spinning", 4, "07:30"), ("boxeo", 3, "20:30")}

# Planes: los que incluyen clases dirigidas pueden reservar
SOCIOS = {
    "SOC-10234": {"nombre": "Enmanuel Alejandro",   "plan": "Premium", "activo": True},
    "SOC-20871": {"nombre": "Javier Núñez",  "plan": "Básico",  "activo": True},   # sin clases
    "SOC-30455": {"nombre": "Lucía Ferrer",  "plan": "Plus",    "activo": False},  # cuota impagada
}
PLANES_CON_CLASES = {"Plus", "Premium"}

MAX_DIAS_ANTELACION = 14

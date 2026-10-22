"""
Webhook de Dialogflow ES para el asistente de voz de FitZone (gimnasio).

Arrancar:
    source .venv/bin/activate
    uvicorn main:app --port 8000
    ngrok http 8000        # y pegar https://xxxx.ngrok-free.app/webhook en Fulfillment

Intenciones con webhook (hay que activar "Enable webhook call for this intent"):
    reservar_clase          -> valida y comprueba disponibilidad
    reservar_clase - yes    -> crea la reserva
    consultar_reserva       -> busca una reserva por codigo
    consulta_documental     -> responde con el texto del OCR (LLM)
    Default Fallback Intent -> igual que consulta_documental
"""

import asyncio
import json
import os
import random
import re
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from google import genai
from google.genai import types
from pydantic import BaseModel

from negocio import CLASES, DIAS, MAX_DIAS_ANTELACION, PLANES_CON_CLASES, SESIONES_COMPLETAS, SOCIOS

load_dotenv(Path(__file__).parent / ".env")

app = FastAPI()

MODELO = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
TIEMPO_MAX_LLM = 3.5   # Dialogflow corta a los 5 s
FICHERO_OCR = Path(__file__).parent / "datos" / "documentos_ocr.json"
CTX_RESERVA = "ctx_reserva_en_curso"
CTX_FOLLOWUP = "reservar_clase-followup"

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

# Regex ESTRICTAS. Las entidades de Dialogflow son mas laxas a proposito
# (aceptan 4-6 digitos, con o sin prefijo): el webhook es quien decide.
RE_SOCIO = re.compile(r"^SOC-\d{5}$")
RE_RESERVA = re.compile(r"^RES-\d{6}$")


def hoy() -> date:
    return datetime.now(ZoneInfo("Europe/Madrid")).date()


def proxima_fecha(weekday: int) -> date:
    h = hoy()
    return h + timedelta(days=(weekday - h.weekday()) % 7 or 7)


# Reservas en memoria (se pierden al reiniciar). Dos de ejemplo para la demo.
RESERVAS = {
    "RES-482913": {"socio": "SOC-10234", "clase": "yoga", "fecha": proxima_fecha(0), "hora": "19:00"},
    "RES-190377": {"socio": "SOC-10234", "clase": "pilates", "fecha": proxima_fecha(1), "hora": "18:00"},
}

# Documentos del OCR (offline, ver ocr.py)

DOCUMENTOS = json.loads(FICHERO_OCR.read_text(encoding="utf-8")) if FICHERO_OCR.exists() else {}
print(f"Documentos cargados: {len(DOCUMENTOS)}")


# Utilidades de respuesta (SSML)

def ssml(texto: str) -> str:
    """
    Convierte texto plano en SSML para el TTS de Dialogflow:
      - escapa &, <, > (lo que escribe el LLM o el usuario no puede romper el XML)
      - '||' -> pausa de 400 ms
      - los codigos SOC-12345 / RES-123456 se leen digito a digito
    """
    texto = escape(texto)
    texto = texto.replace("||", '<break time="400ms"/>')
    texto = re.sub(r"\b(SOC|RES)-(\d+)\b",
                   r'\1 <say-as interpret-as="digits">\2</say-as>', texto)
    return f"<speak>{texto}</speak>"


def responder(texto: str, contextos: list | None = None) -> dict:
    respuesta = {"fulfillmentText": ssml(texto)}
    if contextos:
        respuesta["outputContexts"] = contextos
    return respuesta


def contexto(body: dict, nombre: str, lifespan: int, parametros: dict | None = None) -> dict:
    ctx = {"name": f"{body['session']}/contexts/{nombre}", "lifespanCount": lifespan}
    if parametros is not None:
        ctx["parameters"] = parametros
    return ctx


def cerrar_flujo(body: dict) -> list:
    """Lifespan 0 = borrar contexto. Evita que un 'si' posterior confirme una reserva fallida."""
    return [contexto(body, CTX_RESERVA, 0), contexto(body, CTX_FOLLOWUP, 0)]


def fecha_hablada(f: date) -> str:
    return f"{DIAS[f.weekday()]} {f.day} de {MESES[f.month - 1]}"


def hora_hablada(hhmm: str) -> str:
    h, m = hhmm.split(":")
    return f"las {int(h)} horas" if m == "00" else f"las {int(h)} y {int(m)}"


def parsear_fecha(valor: str) -> date | None:
    try:
        return datetime.fromisoformat(valor).date()
    except (TypeError, ValueError):
        return None


def parsear_hora(valor: str) -> str | None:
    try:
        return datetime.fromisoformat(valor).strftime("%H:%M")
    except (TypeError, ValueError):
        return None


def normalizar_codigo(valor: str, prefijo: str) -> str:
    """'soc 10234' / '10234' / 'SOC-10234' -> 'SOC-10234'."""
    limpio = re.sub(r"[^A-Za-z0-9]", "", str(valor)).upper()
    if limpio.startswith(prefijo):
        limpio = limpio[len(prefijo):]
    return f"{prefijo}-{limpio}"


# reservar_clase

def evaluar_reserva(body: dict, p: dict) -> dict:
    clase = str(p.get("clase", "")).lower()
    fecha = parsear_fecha(p.get("fecha", ""))
    hora = parsear_hora(p.get("hora", ""))
    codigo = normalizar_codigo(p.get("codigo_socio", ""), "SOC")

    def error(texto: str) -> dict:
        return responder(texto, cerrar_flujo(body))

    # 1. Validacion con regex del codigo de socio
    if not RE_SOCIO.match(codigo):
        return error("Ese código de socio no es válido. Tiene que ser SOC seguido de cinco "
                     "números. || Empecemos de nuevo: dime qué clase quieres reservar.")

    socio = SOCIOS.get(codigo)
    if socio is None:
        return error(f"No encuentro ningún socio con el código {codigo}. || "
                     "Puede que lo haya entendido mal. Vuelve a pedirme la reserva y repítemelo.")
    if not socio["activo"]:
        return error(f"{socio['nombre']}, tu cuota tiene un pago pendiente y no puedo reservar "
                     "clases hasta que se regularice. Pásate por recepción.")
    if socio["plan"] not in PLANES_CON_CLASES:
        return error(f"{socio['nombre']}, tu plan {socio['plan']} no incluye clases dirigidas. || "
                     "Con el plan Plus o el Premium sí podrías reservar. ¿Algo más?")

    # 2. Reglas de fecha
    if fecha is None or hora is None or clase not in CLASES:
        return error("No he podido entender la reserva. Vuelve a pedírmela, por favor.")
    if fecha < hoy():
        return error("Esa fecha ya ha pasado. Vuelve a pedirme la reserva con otra fecha.")
    if (fecha - hoy()).days > MAX_DIAS_ANTELACION:
        return error(f"Solo se puede reservar con {MAX_DIAS_ANTELACION} días de antelación. "
                     "Vuelve a pedírmelo con una fecha más cercana.")

    # 3. Existe esa clase ese dia a esa hora?
    horas_del_dia = [h for wd, h in CLASES[clase]["horario"] if wd == fecha.weekday()]
    if not horas_del_dia:
        dias = ", ".join(sorted({DIAS[wd] for wd, _ in CLASES[clase]["horario"]},
                                key=DIAS.index))
        return error(f"El {clase} no se imparte el {DIAS[fecha.weekday()]}. || "
                     f"Las clases son {dias}. Vuelve a pedirme la reserva con otro día.")
    if hora not in horas_del_dia:
        return error(f"El {clase} del {DIAS[fecha.weekday()]} es a {hora_hablada(horas_del_dia[0])}, "
                     "no a esa hora. Vuelve a pedirme la reserva.")

    # 4. Plazas
    if (clase, fecha.weekday(), hora) in SESIONES_COMPLETAS:
        return error(f"Lo siento, el {clase} del {fecha_hablada(fecha)} está completo. || "
                     "Si quieres, pídeme otro día.")

    # Camino bueno: guardamos los datos validados en el contexto y pedimos confirmacion
    datos = {"r_clase": clase, "r_fecha": fecha.isoformat(), "r_hora": hora, "r_socio": codigo}
    return responder(
        f"Perfecto, {socio['nombre']}. || Puedo reservarte {clase} el {fecha_hablada(fecha)} "
        f"a {hora_hablada(hora)}. || ¿Confirmas la reserva?",
        [contexto(body, CTX_RESERVA, 5, datos), contexto(body, CTX_FOLLOWUP, 2)],
    )


def parametros_de_contexto(resultado: dict, nombre: str) -> dict:
    for ctx in resultado.get("outputContexts", []):
        if ctx["name"].endswith(f"/contexts/{nombre}"):
            return ctx.get("parameters", {})
    return {}


def confirmar_reserva(body: dict, resultado: dict) -> dict:
    datos = parametros_de_contexto(resultado, CTX_RESERVA)
    if not all(k in datos for k in ("r_clase", "r_fecha", "r_hora", "r_socio")):
        return responder("No tengo ninguna reserva pendiente. Dime qué clase quieres reservar.")

    codigo = f"RES-{random.randint(100000, 999999)}"
    RESERVAS[codigo] = {"socio": datos["r_socio"], "clase": datos["r_clase"],
                        "fecha": date.fromisoformat(datos["r_fecha"]), "hora": datos["r_hora"]}
    return responder(f"Hecho. || Tu código de reserva es {codigo}. || "
                     "Recuerda que puedes cancelar hasta dos horas antes. ¿Necesitas algo más?",
                     cerrar_flujo(body))   # el flujo acaba aqui; lo cierra el webhook, no Dialogflow


# consultar_reserva

def consultar_reserva(p: dict) -> dict:
    codigo = normalizar_codigo(p.get("codigo_reserva", ""), "RES")
    if not RE_RESERVA.match(codigo):
        return responder("Ese código de reserva no es válido. Son RES seguido de seis números.")
    r = RESERVAS.get(codigo)
    if r is None:
        return responder(f"No encuentro ninguna reserva con el código {codigo}.")
    nombre = SOCIOS[r["socio"]]["nombre"]
    return responder(f"La reserva {codigo} es de {nombre}: {r['clase']} el {fecha_hablada(r['fecha'])} "
                     f"a {hora_hablada(r['hora'])}. || ¿Algo más?")


# Respuesta documental: LLM sobre el texto del OCR

INSTRUCCIONES = """Eres el asistente telefónico del gimnasio FitZone. Respondes en español, en una
o dos frases cortas, porque tu respuesta se convierte en voz. Sin listas ni markdown."""

PLANTILLA = """Responde a la pregunta usando ÚNICAMENTE el texto de los DOCUMENTOS.
Reglas:
- Si la respuesta no aparece en los documentos, pon "respondible": false. NO uses conocimiento propio
  ni deduzcas datos que no estén escritos.
- Si es respondible, "cita" debe ser un fragmento COPIADO LITERALMENTE de los documentos que
  justifique la respuesta.

DOCUMENTOS:
{contexto}

PREGUNTA: {pregunta}"""

NO_SE = ("No dispongo de ese dato en la documentación del gimnasio. || "
         "Puedes llamar a atención al socio, al 912 345 678.")


class Salida(BaseModel):
    respondible: bool
    respuesta: str
    cita: str


cliente = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])


def contexto_documental() -> str:
    # Son pocos documentos: van todos al prompt (context stuffing, sin embeddings).
    return "\n\n".join(f"--- {nombre} ---\n{d['texto']}" for nombre, d in DOCUMENTOS.items())


def cita_esta_en_documentos(cita: str, contexto: str) -> bool:
    """
    Comprueba que la cita del modelo sale de verdad de los documentos. Se compara por
    palabras y en orden, y se exige que casen >= 80%: el OCR deja basura en las tablas
    ('|', 'o') y el modelo a veces junta filas, asi que la copia literal exacta daria
    falsos negativos. Una cita inventada no llega a ese porcentaje.
    """
    palabras = lambda t: re.findall(r"\w+", t.lower())
    cita_p, ctx_p = palabras(cita), palabras(contexto)
    if not cita_p:
        return False
    bloques = SequenceMatcher(None, ctx_p, cita_p, autojunk=False).get_matching_blocks()
    return sum(b.size for b in bloques) / len(cita_p) >= 0.8


async def responder_documental(pregunta: str) -> dict:
    if not DOCUMENTOS:
        return responder(NO_SE)

    contexto = contexto_documental()
    try:
        r = await asyncio.wait_for(
            cliente.aio.models.generate_content(
                model=MODELO,
                contents=PLANTILLA.format(contexto=contexto, pregunta=pregunta),
                config=types.GenerateContentConfig(
                    system_instruction=INSTRUCCIONES,
                    temperature=0.1,
                    max_output_tokens=300,
                    response_mime_type="application/json",
                    response_schema=Salida,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            ),
            timeout=TIEMPO_MAX_LLM,
        )
        salida = Salida.model_validate_json(r.text)
    except Exception as e:   # timeout, cuota, JSON roto...: siempre hay que contestar algo
        print("ERROR LLM:", repr(e))
        return responder("Ahora mismo no puedo consultar la documentación. "
                         "Prueba en un momento o llama al 912 345 678.")

    # Control de alucinaciones: si el modelo dice que no lo sabe, o su cita
    # no aparece de verdad en los documentos, no nos fiamos de la respuesta.
    if not salida.respondible or not cita_esta_en_documentos(salida.cita, contexto):
        print("RAG: sin respuesta fiable ->", salida)
        return responder(NO_SE)
    return responder(salida.respuesta.replace("*", ""))


# Endpoint

@app.post("/webhook")
async def webhook(request: Request):
    body = await request.json()
    resultado = body["queryResult"]
    intencion = resultado["intent"]["displayName"]
    parametros = resultado.get("parameters", {})
    pregunta = resultado.get("queryText", "")

    print("-" * 50)
    print("INTENCION:", intencion)
    print("PARAMETROS:", parametros)
    print("TEXTO:", pregunta)

    if intencion == "reservar_clase":
        if not resultado.get("allRequiredParamsPresent", False):
            return {}
        return evaluar_reserva(body, parametros)

    if intencion == "reservar_clase - yes":
        return confirmar_reserva(body, resultado)

    if intencion == "consultar_reserva":
        if not resultado.get("allRequiredParamsPresent", False):
            return {}
        return consultar_reserva(parametros)

    if intencion in ("consulta_documental", "Default Fallback Intent"):
        return await responder_documental(pregunta)

    return responder("Todavía no sé gestionar esa petición.")


@app.get("/")
def raiz():
    """Para comprobar de un vistazo que el tunel llega hasta aqui."""
    return {"estado": "ok", "documentos_cargados": len(DOCUMENTOS)}

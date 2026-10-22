"""
Genera el export del agente de Dialogflow ES (agente/fitzone-agente.zip), con el
mismo formato que el export de clase (Asegurador-Demo2).

Uso:
    python construir_agente.py https://xxxx.ngrok-free.app/webhook

En Dialogflow: Settings (rueda dentada) -> Export and Import -> Restore from ZIP.
OJO: "Restore" SUSTITUYE todo el agente. Hazlo en un agente nuevo.
"""

import json
import shutil
import sys
import uuid
import zipfile
from pathlib import Path

CARPETA = Path(__file__).parent / "agente"
RAIZ = CARPETA / "fitzone-agente"
ZIP = CARPETA / "fitzone-agente"


def uid(nombre: str) -> str:
    """Ids deterministas: reconstruir el agente no cambia nada."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "fitzone/" + nombre))


def guardar(ruta: str, datos) -> None:
    destino = RAIZ / ruta
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


# Entidades

def entidad(nombre: str, regex: bool, entradas: list[dict]) -> None:
    guardar(f"entities/{nombre}.json", {
        "id": uid("entidad/" + nombre), "name": nombre, "isOverridable": True,
        "isEnum": False, "isRegexp": regex, "automatedExpansion": False,
        "allowFuzzyExtraction": False,
    })
    guardar(f"entities/{nombre}_entries_es.json", entradas)


def sinonimos(valor: str, *otros: str) -> dict:
    return {"value": valor, "synonyms": [valor, *otros]}


def entidades() -> None:
    # Entidad personalizada
    entidad("clase_gimnasio", False, [
        sinonimos("yoga", "clase de yoga", "hatha yoga"),
        sinonimos("pilates", "clase de pilates"),
        sinonimos("spinning", "ciclo indoor", "bici", "clase de spinning"),
        sinonimos("crossfit", "cross fit", "clase de crossfit"),
        sinonimos("zumba", "baile", "clase de zumba"),
        sinonimos("boxeo", "clase de boxeo", "kickboxing"),
    ])
    # Entidades REGEX. Son laxas a proposito (acepta 4-6 digitos con o sin
    # prefijo): el webhook aplica la regex estricta ^SOC-\d{5}$ / ^RES-\d{6}$.
    # Las clases [Ss][Oo][Cc] evitan depender de flags de mayusculas.
    entidad("codigo_socio", True, [sinonimos(r"(?:[Ss][Oo][Cc][\s-]?)?[0-9]{4,6}")])
    entidad("codigo_reserva", True, [sinonimos(r"(?:[Rr][Ee][Ss][\s-]?)?[0-9]{4,7}")])


# Intenciones

def frase(*partes) -> dict:
    """str = texto normal; (texto, alias, entidad) = parametro anotado."""
    data = []
    for p in partes:
        if isinstance(p, str):
            data.append({"text": p, "userDefined": False})
        else:
            data.append({"text": p[0], "alias": p[1], "meta": p[2], "userDefined": True})
    return {"id": str(uuid.uuid4()), "data": data, "isTemplate": False,
            "count": 0, "lang": "es", "updated": 0}


def parametro(nombre: str, entidad_: str, prompts: list[str]) -> dict:
    return {
        "id": uid(f"param/{nombre}/{entidad_}"), "name": nombre, "required": True,
        "dataType": entidad_, "value": f"${nombre}", "defaultValue": "", "isList": False,
        "prompts": [{"lang": "es", "value": p} for p in prompts],
        "promptMessages": [], "noMatchPromptMessages": [], "noInputPromptMessages": [],
        "outputDialogContexts": [],
    }


def intencion(nombre: str, frases: list[dict], *, parametros=(), contextos_entrada=(),
              contextos_salida=(), accion="", respuestas=(), webhook=True,
              evento=None, fallback=False, padre=None) -> None:
    mensaje = {"type": "0", "title": "", "textToSpeech": "", "lang": "es", "condition": ""}
    if respuestas:
        mensaje["speech"] = list(respuestas)
    datos = {
        "id": uid("intent/" + nombre),
        "name": nombre,
        "auto": True,
        "contexts": list(contextos_entrada),
        "responses": [{
            "resetContexts": False,
            "action": accion,
            "affectedContexts": [{"name": n, "lifespan": l} for n, l in contextos_salida],
            "parameters": list(parametros),
            "messages": [mensaje],
            "speech": [],
        }],
        "priority": 500000,
        "webhookUsed": webhook,
        "webhookForSlotFilling": False,
        "fallbackIntent": fallback,
        "events": [{"name": evento}] if evento else [],
        "conditionalResponses": [],
        "condition": "",
        "conditionalFollowupEvents": [],
    }
    if padre:
        datos = {"id": datos["id"], "parentId": uid("intent/" + padre),
                 "rootParentId": uid("intent/" + padre), **{k: v for k, v in datos.items() if k != "id"}}
    guardar(f"intents/{nombre}.json", datos)
    if frases:
        guardar(f"intents/{nombre}_usersays_es.json", frases)


CLASE = lambda t: (t, "clase", "@clase_gimnasio")
FECHA = lambda t: (t, "fecha", "@sys.date")
HORA = lambda t: (t, "hora", "@sys.time")
SOCIO = lambda t: (t, "codigo_socio", "@codigo_socio")
RESERVA = lambda t: (t, "codigo_reserva", "@codigo_reserva")


def intenciones() -> None:
    # Bienvenida: la respuesta va directa en Dialogflow, con SSML
    intencion("Default Welcome Intent", [
        frase(t) for t in ["Hola", "Buenas", "Buenos días", "Buenas tardes", "Hey", "Qué tal"]
    ], webhook=False, evento="WELCOME", accion="input.welcome", respuestas=[
        "<speak>Hola, soy el asistente de FitZone. <break time=\"300ms\"/> Puedo reservarte una "
        "clase, consultar una reserva o resolver dudas sobre normas, tarifas y horarios. "
        "<break time=\"400ms\"/> ¿Qué necesitas?</speak>",
        "<speak>¡Hola! Soy el asistente de FitZone. <break time=\"300ms\"/> ¿Quieres reservar una "
        "clase o tienes alguna pregunta?</speak>",
    ])

    # Fallback: el webhook intenta responder con la documentacion (RAG)
    intencion("Default Fallback Intent", [], fallback=True, accion="input.unknown", respuestas=[
        "<speak>No te he entendido. <break time=\"300ms\"/> ¿Puedes repetirlo?</speak>",
    ])

    # 1. Inicio del flujo multi-turno con contexto: 4 parametros obligatorios
    intencion("reservar_clase", [
        frase("Quiero reservar una clase"),
        frase("Reservar clase"),
        frase("Quiero apuntarme a una clase"),
        frase("Quiero reservar ", CLASE("yoga")),
        frase("Apúntame a ", CLASE("pilates")),
        frase("Reserva ", CLASE("spinning"), " para ", FECHA("mañana")),
        frase("Quiero reservar ", CLASE("zumba"), " el ", FECHA("viernes")),
        frase("Quiero una plaza en ", CLASE("crossfit")),
        frase("Me gustaría reservar ", CLASE("boxeo"), " el ", FECHA("jueves"), " a las ", HORA("20:30")),
        frase("Reserva ", CLASE("yoga"), " el ", FECHA("lunes"), " a las ", HORA("7 de la tarde")),
        frase("Apúntame a ", CLASE("spinning"), " mañana a las ", HORA("7:30")),
        frase("Necesito reservar una clase de ", CLASE("pilates"), " mi código es ", SOCIO("SOC-10234")),
        frase("Quiero reservar ", CLASE("zumba"), " mi número de socio es ", SOCIO("10234")),
    ], parametros=[
        parametro("clase", "@clase_gimnasio", [
            "¿Qué clase quieres reservar? Tenemos yoga, pilates, spinning, crossfit, zumba y boxeo.",
            "¿A qué clase te apunto?"]),
        parametro("fecha", "@sys.date", ["¿Para qué día?", "¿Qué día quieres ir?"]),
        parametro("hora", "@sys.time", ["¿A qué hora?", "¿A qué hora es la clase?"]),
        parametro("codigo_socio", "@codigo_socio", [
            "¿Cuál es tu código de socio?", "Dime tu código de socio, por favor."]),
    ], contextos_salida=[("ctx_reserva_en_curso", 5), ("reservar_clase-followup", 2)])

    # 2. Confirmacion (follow-up si / no) dentro del contexto
    contextos_followup = ["ctx_reserva_en_curso", "reservar_clase-followup"]
    intencion("reservar_clase - yes", [frase(t) for t in [
        "Sí", "Si", "Sí, confirmo", "Confirmo", "Vale", "De acuerdo", "Correcto", "Adelante",
        "Sí, reserva", "Perfecto", "Claro", "Por favor", "Ok"]],
        padre="reservar_clase", contextos_entrada=contextos_followup,
        accion="reservar_clase.reservar_clase-yes")   # sin contextos de salida: el webhook los cierra
    intencion("reservar_clase - no", [frase(t) for t in [
        "No", "No gracias", "Mejor no", "Cancela", "Déjalo", "No lo confirmes", "No, está mal",
        "Cancelar", "Olvídalo"]],
        padre="reservar_clase", contextos_entrada=contextos_followup,
        contextos_salida=[("ctx_reserva_en_curso", 0)],
        accion="reservar_clase.reservar_clase-no", webhook=False, respuestas=[
            "<speak>De acuerdo, no he reservado nada. <break time=\"300ms\"/> "
            "Si quieres, empezamos otra reserva. ¿Necesitas algo más?</speak>"])

    # 3. Consulta de reserva por codigo (regex)
    intencion("consultar_reserva", [
        frase("Quiero consultar mi reserva"),
        frase("Consulta una reserva"),
        frase("Comprueba mi reserva"),
        frase("¿Qué reserva tengo?"),
        frase("Consulta la reserva ", RESERVA("RES-482913")),
        frase("Mi código de reserva es ", RESERVA("RES-190377")),
        frase("Mira la reserva ", RESERVA("482913")),
        frase("Quiero saber el estado de la reserva ", RESERVA("RES-482913")),
    ], parametros=[
        parametro("codigo_reserva", "@codigo_reserva", [
            "¿Cuál es el código de la reserva?", "Dime el código de reserva, por favor."]),
    ], contextos_salida=[])

    # 4. Preguntas sobre la documentacion (el webhook responde con el LLM)
    intencion("consulta_documental", [frase(t) for t in [
        "¿Cuál es el horario del gimnasio?",
        "¿A qué hora abrís?",
        "¿Qué normas hay en el gimnasio?",
        "¿Hay que llevar toalla?",
        "¿Puedo traer a mi perro?",
        "¿Cuánto cuesta el plan premium?",
        "¿Qué incluye el plan plus?",
        "¿Cuál es la cuota de matrícula?",
        "¿Cómo me doy de baja?",
        "¿Hasta cuándo puedo cancelar una reserva?",
        "¿Qué rutina me recomiendas para empezar?",
        "¿Cuántas series hago de press de banca?",
        "¿Cuántos años hay que tener para entrar?",
        "¿Qué días hay clase de yoga?",
        "¿Cuánto cuesta la tarjeta de acceso?",
    ]], contextos_salida=[])


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else "https://REEMPLAZAR.ngrok-free.app/webhook"
    if RAIZ.exists():
        shutil.rmtree(RAIZ)

    guardar("package.json", {"version": "1.0.0"})
    guardar("agent.json", {
        "description": "Asistente de voz de FitZone: reserva de clases y consulta documental",
        "language": "es",
        "shortDescription": "", "examples": "", "linkToDocs": "",
        "displayName": "FitZone",
        "disableInteractionLogs": False, "disableStackdriverLogs": False,
        "defaultTimezone": "Europe/Madrid",
        "webhook": {
            "url": url, "username": "",
            "headers": {"ngrok-skip-browser-warning": "true",
                        "X-Tunnel-Skip-AntiPhishing-Page": "true"},   # ngrok / VS Code dev tunnels
            "available": True, "useForDomains": False,
            "cloudFunctionsEnabled": False, "cloudFunctionsInitialized": False,
        },
        "isPrivate": True, "mlMinConfidence": 0.3, "supportedLanguages": [],
        "enableOnePlatformApi": True, "onePlatformApiVersion": "v2beta1",
        "analyzeQueryTextSentiment": False, "enabledKnowledgeBaseNames": [],
        "knowledgeServiceConfidenceAdjustment": 0.0, "dialogBuilderMode": False,
        "baseActionPackagesUrl": "", "enableSpellCorrection": False,
    })
    entidades()
    intenciones()

    # ZIP solo con ficheros (sin entradas de carpeta), como el export de clase
    zip_ruta = ZIP.with_suffix(".zip")
    with zipfile.ZipFile(zip_ruta, "w", zipfile.ZIP_DEFLATED) as z:
        for fichero in sorted(RAIZ.rglob("*.json")):
            z.write(fichero, fichero.relative_to(RAIZ).as_posix())
    print("Webhook :", url)
    print("Creado  :", zip_ruta)


if __name__ == "__main__":
    main()

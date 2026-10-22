"""
Pruebas del webhook con peticiones simuladas de Dialogflow.
Las dos ultimas llaman de verdad a Gemini (necesitan GOOGLE_API_KEY en .env).

    pytest -v
"""

import re
import sys
import time
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))
import main  # noqa: E402
from main import app, hoy, proxima_fecha  # noqa: E402

cliente = TestClient(app)
cliente.__enter__()   # un unico event loop para toda la sesion (el cliente async de Gemini lo necesita)
SESION = "projects/p/agent/sessions/s1"


def peticion(intencion, parametros=None, texto="", contextos=None):
    return cliente.post("/webhook", json={
        "session": SESION,
        "queryResult": {
            "queryText": texto,
            "intent": {"displayName": intencion},
            "parameters": parametros or {},
            "allRequiredParamsPresent": True,
            "outputContexts": contextos or [],
        },
    }).json()


def reserva(clase="yoga", dia=0, hora="19:00", socio="SOC-10234"):
    fecha = proxima_fecha(dia)
    return peticion("reservar_clase", {
        "clase": clase,
        "fecha": f"{fecha.isoformat()}T12:00:00+02:00",
        "hora": f"2026-01-01T{hora}:00+02:00",
        "codigo_socio": socio,
    })


def texto(resp):
    return resp["fulfillmentText"]


def contextos_vivos(resp):
    return {c["name"].rsplit("/", 1)[1] for c in resp.get("outputContexts", []) if c["lifespanCount"] > 0}


def test_reserva_correcta_pide_confirmacion_y_deja_contexto():
    r = reserva()
    assert "Enmanuel Alejandro" in texto(r) and "¿Confirmas" in texto(r)
    assert texto(r).startswith("<speak>")
    assert contextos_vivos(r) == {"ctx_reserva_en_curso", "reservar_clase-followup"}


def test_codigo_con_formato_distinto_se_normaliza():
    assert "Enmanuel Alejandro" in texto(reserva(socio="10234"))
    assert "Enmanuel Alejandro" in texto(reserva(socio="soc 10234"))


def test_regex_rechaza_codigo_de_longitud_incorrecta():
    r = reserva(socio="1023")
    assert "no es válido" in texto(r)
    assert contextos_vivos(r) == set()      # flujo cerrado: un "si" ya no confirma nada


def test_socio_inexistente():
    assert "No encuentro ningún socio" in texto(reserva(socio="SOC-99999"))


def test_plan_basico_sin_clases():
    assert "no incluye clases" in texto(reserva(socio="SOC-20871"))


def test_cuota_impagada():
    assert "pago pendiente" in texto(reserva(socio="SOC-30455"))


def test_clase_completa():
    r = reserva(clase="spinning", dia=4, hora="07:30")
    assert "completo" in texto(r)


def test_hora_incorrecta_propone_la_real():
    assert "19 horas" in texto(reserva(hora="21:00"))


def test_clase_que_no_se_da_ese_dia():
    assert "no se imparte" in texto(reserva(clase="yoga", dia=1))


def test_antelacion_maxima():
    fecha = hoy() + timedelta(days=30)
    r = peticion("reservar_clase", {
        "clase": "yoga", "fecha": f"{fecha.isoformat()}T12:00:00+02:00",
        "hora": "2026-01-01T19:00:00+02:00", "codigo_socio": "SOC-10234"})
    assert "antelación" in texto(r)


def test_flujo_completo_confirmacion_crea_reserva_consultable():
    ctx = reserva()["outputContexts"]
    r = peticion("reservar_clase - yes", contextos=ctx)
    codigo = "RES-" + re.search(r'RES <say-as interpret-as="digits">(\d{6})', texto(r)).group(1)
    assert codigo in main.RESERVAS
    r2 = peticion("consultar_reserva", {"codigo_reserva": codigo.lower().replace("-", " ")})
    assert "Enmanuel Alejandro" in texto(r2) and "yoga" in texto(r2)


def test_confirmar_sin_reserva_pendiente():
    assert "ninguna reserva pendiente" in texto(peticion("reservar_clase - yes"))


def test_consulta_reserva_inexistente_y_formato_invalido():
    assert "No encuentro" in texto(peticion("consultar_reserva", {"codigo_reserva": "RES-000000"}))
    assert "no es válido" in texto(peticion("consultar_reserva", {"codigo_reserva": "12345"}))


def test_ssml_escapa_y_lee_codigos_en_digitos():
    s = main.ssml("A & B <x> RES-123456")
    assert "&amp;" in s and "&lt;x&gt;" in s and 'interpret-as="digits">123456' in s


# --- LLM real -----------------------------------------------------------

def test_rag_responde_con_los_documentos():
    t0 = time.time()
    r = peticion("consulta_documental", texto="¿Cuánto cuesta el plan Premium?")
    assert "49,90" in texto(r)
    assert time.time() - t0 < 5


@pytest.mark.parametrize("pregunta", [
    "¿Cuánto cuesta un entrenador personal?",
    "¿Qué tiempo hará mañana?",
    "¿Tenéis clases de natación para niños?",
])
def test_rag_no_se_inventa_lo_que_no_esta(pregunta):
    r = peticion("Default Fallback Intent", texto=pregunta)
    assert "No dispongo de ese dato" in texto(r)

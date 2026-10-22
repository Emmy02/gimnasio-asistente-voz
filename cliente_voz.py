"""
Cliente de voz: graba por microfono, lo manda a Dialogflow (STT + intent + TTS
nativos) y reproduce la respuesta hablada.

Uso:
    python cliente_voz.py

Necesita GOOGLE_APPLICATION_CREDENTIALS y DIALOGFLOW_PROJECT_ID en el .env.
"""

import os
import re
import time
import uuid
import wave

import numpy as np
import sounddevice as sd
from dotenv import load_dotenv
from google.cloud import dialogflow

load_dotenv()

PROJECT_ID = os.environ["DIALOGFLOW_PROJECT_ID"]
IDIOMA = "es"
FS = 16000          # Dialogflow espera 16 kHz para LINEAR_16
SEGUNDOS = 4
VOZ = os.environ.get("VOZ_TTS", "es-ES-Neural2-A")   # voz neuronal: mas natural que la estandar

# Un SESSION_ID por conversacion (no por frase): los contextos viven colgados de el.
SESSION_ID = str(uuid.uuid4())

clientes = dialogflow.SessionsClient()
sesion = clientes.session_path(PROJECT_ID, SESSION_ID)


def escuchar(segundos: int = SEGUNDOS) -> bytes:
    print(f"\nHabla ({segundos}s)...")
    audio = sd.rec(int(segundos * FS), samplerate=FS, channels=1, dtype="int16")
    sd.wait()
    return audio.tobytes()


def reproducir(wav_bytes: bytes, fichero: str = "respuesta.wav") -> None:
    """El audio LINEAR_16 que devuelve Dialogflow ya es un WAV completo."""
    with open(fichero, "wb") as f:
        f.write(wav_bytes)
    with wave.open(fichero, "rb") as w:
        muestras = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        tasa = w.getframerate()
    sd.play(muestras, tasa)
    sd.wait()


def salida_de_audio(voz: str | None) -> dialogflow.OutputAudioConfig:
    config = dialogflow.OutputAudioConfig(
        audio_encoding=dialogflow.OutputAudioEncoding.OUTPUT_AUDIO_ENCODING_LINEAR_16
    )
    if voz:
        config.synthesize_speech_config = dialogflow.SynthesizeSpeechConfig(
            voice=dialogflow.VoiceSelectionParams(name=voz)
        )
    return config


def consultar(query_input: dialogflow.QueryInput, audio_bytes: bytes | None = None):
    """Llama a detect_intent. Si la voz elegida no existe, reintenta con la voz por defecto."""
    for voz in (VOZ, None):
        peticion = {"session": sesion, "query_input": query_input,
                    "output_audio_config": salida_de_audio(voz)}
        if audio_bytes:
            peticion["input_audio"] = audio_bytes
        try:
            return clientes.detect_intent(request=peticion)
        except Exception as e:
            if voz is None:
                raise
            print(f"(voz {voz} no disponible: {e}. Uso la voz por defecto)")


def mostrar(respuesta, t0: float) -> None:
    r = respuesta.query_result
    segundos = time.time() - t0
    if r.query_text:
        print(f"  Has dicho : {r.query_text}")
    print(f"  Intención : {r.intent.display_name} ({r.intent_detection_confidence:.2f})")
    print(f"  Responde  : {re.sub(r'<[^>]+>', '', r.fulfillment_text).strip()}")
    aviso = "  <-- supera los 5 s" if segundos > 5 else ""
    print(f"  Latencia  : {segundos:.1f} s{aviso}")
    if respuesta.output_audio:
        reproducir(respuesta.output_audio)


def main() -> None:
    print("=" * 55)
    print("FitZone · asistente de voz")
    print(f"Proyecto : {PROJECT_ID}   Voz: {VOZ}")
    print("Enter para hablar, 'q' + Enter para salir.")
    print("=" * 55)

    # El agente saluda primero (evento WELCOME)
    t0 = time.time()
    mostrar(consultar(dialogflow.QueryInput(
        event=dialogflow.EventInput(name="WELCOME", language_code=IDIOMA))), t0)

    entrada = dialogflow.QueryInput(audio_config=dialogflow.InputAudioConfig(
        audio_encoding=dialogflow.AudioEncoding.AUDIO_ENCODING_LINEAR_16,
        language_code=IDIOMA,
        sample_rate_hertz=FS,
    ))

    while True:
        if input("\n> ").strip().lower() == "q":
            break
        audio = escuchar()
        t0 = time.time()
        mostrar(consultar(entrada, audio), t0)


if __name__ == "__main__":
    main()

# FitZone: asistente de voz para un gimnasio

## Arquitectura

![Arquitectura](docs/arquitectura.png)

## Cómo ejecutarlo

```bash
cd ~/Pontia/gimnasio-asistente-voz
source .venv/bin/activate
```

1. **Webhook** (terminal 1):
   ```bash
   uvicorn main:app --port 8000
   ```
2. **Túnel público** (terminal 2). Copia la dirección `https://xxxx.trycloudflare.com` que imprime:
   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```
3. **Agente** (terminal 3, con tu dirección y `/webhook` al final):
   ```bash
   python construir_agente.py https://xxxx.trycloudflare.com/webhook
   ```
   En Dialogflow: ⚙ → Export and Import → Restore from ZIP → `agente/fitzone-agente.zip`. Después ⚙ → ML Settings → Train.
4. **Voz**:
   ```bash
   python cliente_voz.py
   ```
   Enter para hablar (4 s). Di el código seguido: "SOC 10234".

Si la dirección del túnel cambia, pégala en Dialogflow → Fulfillment → URL y guarda.

## Usuarios de prueba

| Código | Socio | Resultado |
| --- | --- | --- |
| `SOC-10234` | Enmanuel Alejandro (Premium) | Puede reservar |
| `SOC-20871` | Javier Núñez (Básico) | "Tu plan Básico no incluye clases dirigidas." |
| `SOC-30455` | Lucía Ferrer (Plus, cuota impagada) | "Tu cuota tiene un pago pendiente." |

Reserva de ejemplo para consultar: `RES-482913`.

## Ejemplo de conversación completa

**Usuario:** Hola
**Asistente:** Hola, soy el asistente de FitZone. Puedo reservarte una clase, consultar una reserva o resolver dudas sobre normas, tarifas y horarios. ¿Qué necesitas?

**Usuario:** Quiero reservar una clase de yoga
**Asistente:** ¿Para qué día?
**Usuario:** El lunes
**Asistente:** ¿A qué hora?
**Usuario:** A las 7 de la tarde
**Asistente:** ¿Cuál es tu código de socio?
**Usuario:** SOC 10234
**Asistente:** Perfecto, Enmanuel Alejandro. Puedo reservarte yoga el lunes 26 de octubre a las 19 horas. ¿Confirmas la reserva?
**Usuario:** Sí
**Asistente:** Hecho. Tu código de reserva es RES-123456. Recuerda que puedes cancelar hasta dos horas antes. ¿Necesitas algo más?

**Usuario:** Consulta la reserva RES 482913
**Asistente:** La reserva RES-482913 es de Enmanuel Alejandro: yoga el lunes 26 de octubre a las 19 horas. ¿Algo más?

**Usuario:** ¿Hay que llevar toalla?
**Asistente:** Sí, es obligatorio usar toalla en la sala de máquinas.

**Usuario:** ¿Cuánto cuesta un entrenador personal?
**Asistente:** No dispongo de ese dato en la documentación del gimnasio. Puedes llamar a atención al socio, al 912 345 678.

### Con los otros dos usuarios

Si en la reserva se dice otro código de socio, la conversación es igual hasta ese punto:

**Usuario:** SOC 20871
**Asistente:** Javier Núñez, tu plan Básico no incluye clases dirigidas. Con el plan Plus o el Premium sí podrías reservar. ¿Algo más?

**Usuario:** SOC 30455
**Asistente:** Lucía Ferrer, tu cuota tiene un pago pendiente y no puedo reservar clases hasta que se regularice. Pásate por recepción.

## Vídeo de demostración

La grabación de la conversación por voz está en la carpeta [`video/`](video/).

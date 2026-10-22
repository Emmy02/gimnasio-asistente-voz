# FitZone: asistente de voz para un gimnasio

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
   Enter para hablar (6 s). Di el código seguido: "SOC 10234".

Si la dirección del túnel cambia, pégala en Dialogflow → Fulfillment → URL y guarda.

## Los 3 usuarios de prueba

| Código | Socio | Resultado |
| --- | --- | --- |
| `SOC-10234` | Enmanuel Alejandro (Premium) | Puede reservar |
| `SOC-20871` | Javier Núñez (Básico) | "Tu plan no incluye clases dirigidas" |
| `SOC-30455` | Lucía Ferrer (Plus, impagado) | "Tu cuota tiene un pago pendiente" |

Reserva de ejemplo para consultar: `RES-482913`.

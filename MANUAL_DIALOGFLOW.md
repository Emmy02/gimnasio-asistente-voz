# Montar el agente a mano en la consola de Dialogflow

Agente: `pontia-exercise` (https://dialogflow.cloud.google.com/#/agent/pontia-exercise/). Idioma: **es**.
Tiempo estimado: 40-60 minutos. Sigue el orden: entidades → webhook → intenciones.

> Tu agente ya tiene intenciones de clase (`solicitar_grua`, `consulta_coberturas`...). Pueden convivir con las nuevas, pero para la entrega es más limpio borrarlas (menos intenciones que confundan a Dialogflow). Reutiliza `Default Welcome Intent` y `Default Fallback Intent`.

## 0. Antes de tocar la consola

1. Arranca el webhook y el túnel:
   ```bash
   cd ~/Pontia/gimnasio-asistente-voz && source .venv/bin/activate
   uvicorn main:app --port 8000
   ngrok http 8000          # en otra terminal; copia la URL https://xxxx.ngrok-free.app
   ```
2. Comprueba en el navegador que `https://xxxx.ngrok-free.app/` devuelve `{"estado":"ok","documentos_cargados":4}`.

## 1. Entidades (menú *Entities* → *Create Entity*)

### 1.1 `clase_gimnasio` (personalizada)
Marca *Define synonyms* y añade 6 filas (valor de referencia | sinónimos):

| Valor | Sinónimos |
| --- | --- |
| `yoga` | `yoga`, `clase de yoga`, `hatha yoga` |
| `pilates` | `pilates`, `clase de pilates` |
| `spinning` | `spinning`, `ciclo indoor`, `bici`, `clase de spinning` |
| `crossfit` | `crossfit`, `cross fit`, `clase de crossfit` |
| `zumba` | `zumba`, `baile`, `clase de zumba` |
| `boxeo` | `boxeo`, `clase de boxeo`, `kickboxing` |

Save.

### 1.2 `codigo_socio` (REGEX)
- Menú de los tres puntos (arriba a la derecha) → **Switch to regexp mode** (o marca *Regexp entity*).
- Una única entrada:
  ```
  (?:[Ss][Oo][Cc][\s-]?)?[0-9]{4,6}
  ```
- Save.

### 1.3 `codigo_reserva` (REGEX)
- Igual, modo regexp. Una única entrada:
  ```
  (?:[Rr][Ee][Ss][\s-]?)?[0-9]{4,7}
  ```
- Save.

> Son laxas a propósito: el webhook aplica después la regex estricta (`^SOC-\d{5}$`, `^RES-\d{6}$`).

## 2. Webhook (menú *Fulfillment*)

- **Webhook: Enabled.**
- URL: `https://xxxx.ngrok-free.app/webhook` (con `/webhook` al final).
- Headers: clave `ngrok-skip-browser-warning`, valor `true`.
- Save. (Si reinicias ngrok la URL cambia: hay que actualizarla aquí.)

## 3. Intenciones

En **cada** intención con webhook hay que abrir *Fulfillment* (abajo del todo) y activar **Enable webhook call for this intent**. Sin eso, silencio total.

### 3.1 `Default Welcome Intent` (ya existe)
- Training phrases: déjalas.
- *Responses* → borra las que haya y añade dos (pestaña *Default*, texto):
  1. `<speak>Hola, soy el asistente de FitZone. <break time="300ms"/> Puedo reservarte una clase, consultar una reserva o resolver dudas sobre normas, tarifas y horarios. <break time="400ms"/> ¿Qué necesitas?</speak>`
  2. `<speak>¡Hola! Soy el asistente de FitZone. <break time="300ms"/> ¿Quieres reservar una clase o tienes alguna pregunta?</speak>`
- Webhook: **no** activarlo. Save.

### 3.2 `Default Fallback Intent` (ya existe)
- Responses: `<speak>No te he entendido. <break time="300ms"/> ¿Puedes repetirlo?</speak>`
- Fulfillment: **activa** *Enable webhook call for this intent* (el webhook intenta contestar con los documentos). Save.

### 3.3 `reservar_clase` (nueva, *Create Intent*)

**Contexts → Output contexts:** añade `ctx_reserva_en_curso` con lifespan **5**. (`reservar_clase-followup` lo añade Dialogflow solo al crear los follow-ups del paso 3.4; si ya lo ves, déjalo.)

**Training phrases** (13). En las que tienen `[parámetro]` selecciona el texto y asígnale la entidad indicada; los alias deben llamarse exactamente como el parámetro.

```
Quiero reservar una clase
Reservar clase
Quiero apuntarme a una clase
Quiero reservar [yoga]                                 → clase
Apúntame a [pilates]                                   → clase
Reserva [spinning] para [mañana]                       → clase, fecha
Quiero reservar [zumba] el [viernes]                   → clase, fecha
Quiero una plaza en [crossfit]                         → clase
Me gustaría reservar [boxeo] el [jueves] a las [20:30] → clase, fecha, hora
Reserva [yoga] el [lunes] a las [7 de la tarde]        → clase, fecha, hora
Apúntame a [spinning] mañana a las [7:30]              → clase, hora
Necesito reservar una clase de [pilates] mi código es [SOC-10234]   → clase, codigo_socio
Quiero reservar [zumba] mi número de socio es [10234]  → clase, codigo_socio
```

**Action and parameters** (tabla; marca **REQUIRED** en las cuatro):

| Parameter name | Entity | Value | Prompts (añade los dos) |
| --- | --- | --- | --- |
| `clase` | `@clase_gimnasio` | `$clase` | `¿Qué clase quieres reservar? Tenemos yoga, pilates, spinning, crossfit, zumba y boxeo.` / `¿A qué clase te apunto?` |
| `fecha` | `@sys.date` | `$fecha` | `¿Para qué día?` / `¿Qué día quieres ir?` |
| `hora` | `@sys.time` | `$hora` | `¿A qué hora?` / `¿A qué hora es la clase?` |
| `codigo_socio` | `@codigo_socio` | `$codigo_socio` | `¿Cuál es tu código de socio?` / `Dime tu código de socio, por favor.` |

**Responses:** déjalo vacío (la respuesta la genera el webhook).
**Fulfillment:** activa *Enable webhook call for this intent*. **No** actives *for slot filling*.
Save.

### 3.4 Confirmación sí / no (follow-ups de `reservar_clase`)

En la lista de intenciones pasa el ratón sobre `reservar_clase` → **Add follow-up intent** → **Yes**. Dialogflow crea `reservar_clase - yes`. Repite con **No** → `reservar_clase - no`.

**`reservar_clase - yes`**
- Input contexts: ya trae `reservar_clase-followup`. **Añade** `ctx_reserva_en_curso`.
- Training phrases: `Sí`, `Si`, `Sí, confirmo`, `Confirmo`, `Vale`, `De acuerdo`, `Correcto`, `Adelante`, `Sí, reserva`, `Perfecto`, `Claro`, `Por favor`, `Ok`.
- Output contexts: **no cambies nada** (el webhook cierra el flujo; si lo borras tú aquí, el webhook no encuentra los datos de la reserva).
- Responses: vacío.
- Fulfillment: **activa** *Enable webhook call for this intent*. Save.

**`reservar_clase - no`**
- Input contexts: `reservar_clase-followup` + **añade** `ctx_reserva_en_curso`.
- Training phrases: `No`, `No gracias`, `Mejor no`, `Cancela`, `Déjalo`, `No lo confirmes`, `No, está mal`, `Cancelar`, `Olvídalo`.
- Output contexts: `ctx_reserva_en_curso` con lifespan **0**.
- Responses: `<speak>De acuerdo, no he reservado nada. <break time="300ms"/> Si quieres, empezamos otra reserva. ¿Necesitas algo más?</speak>`
- Fulfillment: **no** activar el webhook. Save.

### 3.5 `consultar_reserva`

**Training phrases:**
```
Quiero consultar mi reserva
Consulta una reserva
Comprueba mi reserva
¿Qué reserva tengo?
Consulta la reserva [RES-482913]                       → codigo_reserva
Mi código de reserva es [RES-190377]                   → codigo_reserva
Mira la reserva [482913]                               → codigo_reserva
Quiero saber el estado de la reserva [RES-482913]      → codigo_reserva
```
**Parameters:** `codigo_reserva` | `@codigo_reserva` | `$codigo_reserva` | **REQUIRED** | prompts: `¿Cuál es el código de la reserva?` / `Dime el código de reserva, por favor.`
**Responses:** vacío. **Fulfillment:** activa el webhook. Save.

### 3.6 `consulta_documental`

**Training phrases** (sin parámetros):
```
¿Cuál es el horario del gimnasio?
¿A qué hora abrís?
¿Qué normas hay en el gimnasio?
¿Hay que llevar toalla?
¿Puedo traer a mi perro?
¿Cuánto cuesta el plan premium?
¿Qué incluye el plan plus?
¿Cuál es la cuota de matrícula?
¿Cómo me doy de baja?
¿Hasta cuándo puedo cancelar una reserva?
¿Qué rutina me recomiendas para empezar?
¿Cuántas series hago de press de banca?
¿Cuántos años hay que tener para entrar?
¿Qué días hay clase de yoga?
¿Cuánto cuesta la tarjeta de acceso?
```
**Responses:** vacío. **Fulfillment:** activa el webhook. Save.

## 4. Entrenar y probar

1. Pestaña **Training** (o el botón del engranaje → ML Settings → *Train*): entrena a mano. Si algo "no se dispara", sospecha primero de esto.
2. Simulador de la derecha, en este orden:
   - `hola`
   - `quiero reservar una clase de yoga` → te pregunta día → `el lunes` → hora → `a las 7 de la tarde` → código → `SOC 10234` → debe resumir y pedir confirmación → `sí` → te da `RES-xxxxxx`.
   - `consulta la reserva RES 482913`
   - `¿hay que llevar toalla?`
   - `¿cuánto cuesta un entrenador personal?` → "No dispongo de ese dato…"
3. En la terminal de `uvicorn` verás cada llamada (`INTENCION:`, `PARAMETROS:`). En el simulador, las respuestas se ven con las etiquetas `<speak>` (es normal: es SSML para la voz).
4. Voz: `python cliente_voz.py` (necesita el mismo proyecto en `DIALOGFLOW_PROJECT_ID` del `.env`).

## Si falla

| Síntoma | Causa probable |
| --- | --- |
| Silencio total / respuesta vacía | Falta *Enable webhook call for this intent* en esa intención |
| La intención no se dispara | No entrenado → nombre del input context distinto → pocas frases |
| `reservar_clase - yes` dice "no tengo ninguna reserva pendiente" | Le has puesto un output context con lifespan 0, o falta `ctx_reserva_en_curso` como input context |
| Un "sí" tras un error confirma algo | No debería pasar: el webhook cierra los contextos al fallar. Revisa que el webhook esté activo |
| El simulador no llega al webhook | URL de ngrok cambiada o sin `/webhook` |
| "Ahora mismo no puedo consultar la documentación" | Falla Gemini (`GOOGLE_API_KEY`) o tarda más de 3,5 s: mira el log de uvicorn (`ERROR LLM:`) |

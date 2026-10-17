# Cómo funciona

Esto es un laboratorio con datos inventados de Taller Aurora, una cooperativa ficticia. El "cerebro" que corre en CI es un guion, no un modelo. Sirve para mostrar las herramientas, las compuertas y las reglas, no la calidad de un modelo.

## Analogía

Pensalo como una recepción. La persona anota el turno en lápiz, te lo lee entero (día, hora y zona), y recién cuando vos decís que sí se lo pasa a quien manda el correo. Si nadie aprueba, el correo queda en una bandeja de salida que no sale a ningún lado.

## Paso a paso

1. Abrís una sesión con una candidata, su zona horaria y un reloj fijo. El reloj no es el reloj de la pared: los tests lo adelantan cuando quieren ver un hold vencido.
2. El guion pide disponibilidad. El calendario en memoria devuelve como máximo 3 huecos, con duración de 45 minutos y un buffer de 15.
3. El texto que ves lista como máximo tres huecos numerados, con zona y offset, por ejemplo `1) mar 20/10 10:00 (ART, UTC-3)`. Si una respuesta trae una hora sin zona, no te la muestra: se la devuelve al modelo para que la reescriba, con un reintento acotado.
4. Un "Sí, confirmo.", un "la 1" o un "ese" aceptan el último hueco ofrecido. Ese hueco queda guardado como `pending_slot` y el modelo lo ve en el contexto, así que no vuelve a preguntar cuál era. Si no confirmás, no se reserva.
5. El correo de invitación es una herramienta externa. Sin una aprobación del recruiter atada al hash de esos argumentos, no se ejecuta. La aprobación de las 10:00 no sirve para las 11:00. En este repo esa aprobación es simulada. En producción tiene que llegar por un canal autenticado, y este repo no lo implementa.
6. Si el recruiter rechaza, la acción termina y el agente te dice qué sigue. No reintenta el mismo envío a escondidas.
7. Al final, un chequeo lee la traza y pregunta si se cumplieron las invariantes. No pide la secuencia exacta de llamadas.

## Glosario

| Palabra | Qué es |
| --- | --- |
| Hold | Una reserva temporal. Se vence si el reloj inyectado avanza más que el TTL. |
| Outbox | Lista en memoria de correos que "se mandarían". No hay servidor de mail. |
| Hash de parámetros | Una huella de la herramienta y sus argumentos. La aprobación cubre esa huella, no "un mail parecido". |
| Invariante | Una propiedad de la traza. Por ejemplo: no hay dos turnos pisados. |
| Kill switch | `EXTERNAL_TOOLS_ENABLED=0`. Con eso apagado, ninguna herramienta externa corre, ni siquiera en el modo de regresión. |
| Provider scripted | El guion determinista. No es un modelo. |

Mirá la traza si algo no cierra. Fijate que el correo que vas a aprobar sea el mismo hueco que la persona confirmó. Tenés el kill switch si hace falta frenar todo envío.

## Límites, en serio

- Verificación independiente del 2026-10-17, grok-4.20-0309-non-reasoning, `booking_end_to_end` sobre main tras el arreglo del envío aprobado, un solo modelo, muestra chica, sin tasa. Primera muestra n=5: 5/5 PASS con aprobación simulada (outbox=1, origin=approval, mismo param_hash), cerca de US$0.11. Tres corridas más el mismo día: PASS 3/3, US$0.054. Juntas eran 8/8. La verificación externa del mismo día (VERIFY_REPORT_9, HEAD `4c2170d`, costo = `usage.cost_in_usd_ticks`) sumó 3 corridas: PASS 3/3, US$0.02512 + US$0.02060 + US$0.02156 = US$0.06728 (28 llamadas, 0 errores). Eso era 11/11. La verificación externa de la ampliación de verbos (VERIFY_REPORT_10, HEAD `bb314c9`, costo = `usage.cost_in_usd_ticks`) sumó 3 corridas: PASS 3/3, US$0.01766 + US$0.02300 + US$0.01312 = US$0.05378 (27 llamadas, 0 errores). Eso era 14/14. La verificación externa del detector con `\bno\b` (VERIFY_REPORT_11, HEAD `c525227`, costo = `usage.cost_in_usd_ticks`) sumó 1 PASS: US$0.0205215, 10 llamadas, 35629 tokens in (24576 cacheados), 716 out. Acumulado 15/15 PASS con aprobación simulada (esos 14 más este 1), n=15. El gasto combinado de ese informe es cerca de US$0.0770 e incluye otros repos. Cuatro corridas más quedaron INCOMPLETE por el tope del verificador (US$0.028 ×3 y US$0.035 ×1), no son PASS ni FAIL. Eso no prueba que el modelo reintente la herramienta: el runtime ejecuta la llamada aprobada. El ledger, sin `LLM_PRICE_CACHED_PER_MTOK`, cobra el cache al precio completo de entrada: en ese PASS estima cerca de US$0.046 contra US$0.0205215 en ticks, cerca de 2,3×. La reserva previa a la llamada sigue usando el precio completo, así que un tope bajo (menos de unos US$0.06) puede abortar un PASS. El reparto por corrida y los tokens de los 8 primeros no quedaron registrados. Un chequeo adversarial offline del mismo día no encontró bypass del gate humano en 11 casos. En producción la aprobación tiene que llegar por un canal autenticado; este repo no lo implementa. Antes del arreglo, otra muestra n=8: 0/8 PASS, 8/8 INCOMPLETE, outbox=0, cerca de US$0.15. La muestra n=6 y la de `happy_path` (0 reservas) quedan como historia.
- `no_cross_candidate_access` no ve un mail ofuscado, un mail partido con espacios, ni un nombre de pila solo. Chequeo offline del 2026-10-17: 6/6 fugas directas detectadas y 3 controles limpios (n chico). `no_send_claim_without_outbox` en un set nuevo, bandeja vacía, antes de contar `ningún`/`nada` (VERIFY_REPORT_11, HEAD `c525227`, n=20, muestra chica, no concluyente): recall 18/20, falsos positivos 1/20. El falso positivo medido es "Ningún mail salió todavía…". Tras un envío real, 0/20 de ese set quedaron marcadas. VERIFY_REPORT_10, otra lista, fue 15/20 y 1/20; no son comparables. El recall posterior a contar `ningún`/`nada` está no medido todavía. El comando `live` imprime `expect_failures`. La suite de tests borra `LIVE_LLM` y las claves, y falla si un test abre un socket.
- Una fecha sin offset, como `2026-04-14T00:00:00`, se rechaza. No se interpreta como UTC ni como Buenos Aires. El ejemplo válido es `2026-10-20T10:00:00-03:00`.
- El calendario y los mails son de juguete. Los nombres (Candidata Uno, Ana Luz) son ficticios.
- El hit del buscador de FAQ es sobre 30 preguntas escritas junto con los textos. No es generalización.
- Dockerfile está en el repo. No se construyó en CI.

## Guion de dos minutos

"El modelo razona; el sistema alrededor lo hace confiable. Acá el modelo ni siquiera está: en CI hay un guion. Lo que sí está es el calendario que rechaza el doble turno, la confirmación de la persona sobre el hueco exacto, y la aprobación del recruiter atada al hash del correo. Si apagás las compuertas a propósito, el chequeo sale en 1. Eso es lo que quiero mostrar: las invariantes agarran el caso roto. Un modelo de verdad, cuando exista, tiene que pasar por las mismas puertas."

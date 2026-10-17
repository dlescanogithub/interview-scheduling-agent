# Cómo funciona

Esto es un laboratorio con datos inventados de Taller Aurora, una cooperativa ficticia. El "cerebro" que corre en CI es un guion, no un modelo. Sirve para mostrar las herramientas, las compuertas y las reglas, no la calidad de un modelo.

## Analogía

Pensalo como una recepción. La persona anota el turno en lápiz, te lo lee entero (día, hora y zona), y recién cuando vos decís que sí se lo pasa a quien manda el correo. Si nadie aprueba, el correo queda en una bandeja de salida que no sale a ningún lado.

## Paso a paso

1. Abrís una sesión con una candidata, su zona horaria y un reloj fijo. El reloj no es el reloj de la pared: los tests lo adelantan cuando quieren ver un hold vencido.
2. El guion pide disponibilidad. El calendario en memoria devuelve como máximo 3 huecos, con duración de 45 minutos y un buffer de 15.
3. El texto que ves lista como máximo tres huecos numerados, con zona y offset, por ejemplo `1) mar 20/10 10:00 (ART, UTC-3)`. Si una respuesta trae una hora sin zona, no te la muestra: se la devuelve al modelo para que la reescriba, con un reintento acotado.
4. Un "Sí, confirmo.", un "la 1" o un "ese" aceptan el último hueco ofrecido. Ese hueco queda guardado como `pending_slot` y el modelo lo ve en el contexto, así que no vuelve a preguntar cuál era. Si no confirmás, no se reserva.
5. El correo de invitación es una herramienta externa. Sin una aprobación del recruiter atada al hash de esos argumentos, no se ejecuta. La aprobación de las 10:00 no sirve para las 11:00.
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

- El 2026-10-17 se corrió `happy_path` tres veces con un modelo real: INCOMPLETE 3/3, exit 3, invariantes OK, 0 reservas, sin crashes. Los slots numerados salieron con zona. "Sí, confirmo." dejó el hold de la opción 1 y pidió una segunda confirmación; el escenario se corta ahí, así que no hubo `book_slot`. El costo de las tres corridas fue US$0.00875 + US$0.00872 + US$0.00844, cerca de US$0.026, cuatro llamadas cada una. Para ver una reserva de punta a punta hay que usar `booking_end_to_end`. Esa re-verificación en vivo está pendiente.
- Una fecha sin offset, como `2026-04-14T00:00:00`, se rechaza. No se interpreta como UTC ni como Buenos Aires. El ejemplo válido es `2026-10-20T10:00:00-03:00`.
- El calendario y los mails son de juguete. Los nombres (Candidata Uno, Ana Luz) son ficticios.
- El hit del buscador de FAQ es sobre 30 preguntas escritas junto con los textos. No es generalización.
- Dockerfile está en el repo. No se construyó en CI.

## Guion de dos minutos

"El modelo razona; el sistema alrededor lo hace confiable. Acá el modelo ni siquiera está: en CI hay un guion. Lo que sí está es el calendario que rechaza el doble turno, la confirmación de la persona sobre el hueco exacto, y la aprobación del recruiter atada al hash del correo. Si apagás las compuertas a propósito, el chequeo sale en 1. Eso es lo que quiero mostrar: las invariantes agarran el caso roto. Un modelo de verdad, cuando exista, tiene que pasar por las mismas puertas."

"""
Bot de Telegram para Analisis de Quinielas
Basado en analisis_quinielas.py

Uso:
  1. Consigue un token de @BotFather en Telegram
  2. Crea un archivo bot_token.txt con el token
  3. Ejecuta: python bot_quinielas.py
"""

import logging
import asyncio
import secrets
from datetime import timedelta
import os
import sys

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

from analisis_quinielas import cargar_datos, construir_indices, inverso, scrapear_hoy, predecir_b1, cargar_secuencias, precomputar_cache_anguila, predecir_anguila_auto, predecir_loteria_secuencia, buscar_loterias, metodo_super_kino, b2b3_frecuentes_fecha, b1s_de_fecha, super_pale_dia_como_hoy, super_pale_pares, hoy_dr, actualizar_kino, guardar_prediccion_kino, aciertos_prediccion_ayer, cruzar_secuencias_lotseq, b1_ayer_loteria, transformar_reverso, actualizar_powerball, predecir_powerball_desde_ultimo

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

_script_dir = os.path.dirname(os.path.abspath(__file__))
RUTA_SECUENCIAS = os.path.join(_script_dir, "03-10-25-05-66-00.txt")

METHOD, NUMBERS, LOTERIA = range(3)

def teclado_principal():
    """Menu principal. Se construye en cada llamada para que la fecha del boton SUPER PALE sea siempre la de hoy."""
    hoy = hoy_dr()
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("\U0001f3b2 PREDICCION MANUAL", callback_data="manual")],
        [InlineKeyboardButton("\U0001f50d B2/B3", callback_data="b2b3_menu")],
        [InlineKeyboardButton("\U0001f41d ANGUILA SIGUIENTE HORA", callback_data="anguila")],
        [InlineKeyboardButton(f"\U0001f9e7 SUPER PALE UN DIA COMO HOY ({hoy.day}/{hoy.month})", callback_data="super_pale")],
        [InlineKeyboardButton("\U0001f3e0 SELECCIONAR LOTERIA", callback_data="loteria")],
        [InlineKeyboardButton("\U0001f3af SECUENCIAS x LOTSEQ", callback_data="secuencias")],
        [InlineKeyboardButton("\U0001f3c6 SUPER KINO", callback_data="super_kino")],
        [InlineKeyboardButton("POWERBALL", callback_data="powerball")],
    ])
def teclado_b2b3():
    """Submenu B2/B3 con las fechas reales de hoy y ayer."""
    hoy = hoy_dr()
    ayer = hoy - timedelta(days=1)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📅 B2/B3 de HOY {hoy.day}/{hoy.month} (lo que ya salio)", callback_data="b2b3_hoy")],
        [InlineKeyboardButton(f"📄 B2/B3 de AYER {ayer.day}/{ayer.month}", callback_data="b2b3_ayer")],
        [InlineKeyboardButton("🔙 Atras", callback_data="atras")],
    ])


ATRAS = InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f519 Atras", callback_data="atras")]])
POWERBALL_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("METODO 1 - DESDE ULTIMO SORTEO", callback_data="powerball_metodo1")],
    [InlineKeyboardButton("METODO 2 - BARAJADO", callback_data="powerball_metodo2")],
    [InlineKeyboardButton("Atras", callback_data="atras")],
])

POWERBALL_WHITE_MAX = 69
POWERBALL_RED_MAX = 26
POWERBALL_WHITE_COUNT = 5


def generar_powerball_metodo1():
    rng = secrets.SystemRandom()
    blancos = tuple(sorted(rng.sample(range(1, POWERBALL_WHITE_MAX + 1), POWERBALL_WHITE_COUNT)))
    rojo = rng.randint(1, POWERBALL_RED_MAX)
    return blancos, rojo


def generar_powerball_metodo2():
    blancos = list(range(1, POWERBALL_WHITE_MAX + 1))
    for indice in range(len(blancos) - 1, 0, -1):
        otro = secrets.randbelow(indice + 1)
        blancos[indice], blancos[otro] = blancos[otro], blancos[indice]
    return tuple(sorted(blancos[:POWERBALL_WHITE_COUNT])), secrets.randbelow(POWERBALL_RED_MAX) + 1


def formatear_powerball(blancos, rojo, metodo, base=None):
    nombres = {
        1: "DESDE EL ULTIMO SORTEO" if base else "ALEATORIO (sin datos del ultimo sorteo)",
        2: "BARAJADO UNIFORME",
    }
    lineas = [
        "POWERBALL",
        f"*Metodo {metodo}: {nombres[metodo]}*",
        "",
    ]
    if base:
        base_txt = " ".join(f"{n:02d}" for n in base["base_blancos"])
        lineas += [
            f"Base (ultimo sorteo {base['base_fecha'].strftime('%d/%m/%Y')}): `{base_txt}` + `{base['base_rojo']:02d}`",
            f"Coincidencias historicas: {base['muestras']} sorteos (ventana {base['ventana']})",
            "",
        ]
    lineas += [
        f"Blancos: `{' '.join(f'{numero:02d}' for numero in blancos)}`",
        f"Powerball: `{rojo:02d}`",
        "",
    ]
    if metodo == 1 and base:
        lineas.append("El metodo 1 usa el ultimo sorteo como base, pero el sorteo es independiente: no mejora la probabilidad real.")
    else:
        lineas.append("Este metodo es aleatorio y no mejora la probabilidad del sorteo.")
    return "\n".join(lineas)


def cargar_token():
    import os
    token = os.environ.get("BOT_TOKEN")
    if token:
        return token
    try:
        with open("bot_token.txt") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

async def _editar(query, texto, reply_markup=None, parse_mode=None):
    """edit_message_text que nunca rompe el flujo del boton.

    - Si el texto es identico al del mensaje, Telegram lanza "Message is not
      modified": se ignora (el mensaje ya muestra ese resultado).
    - Si falla el parseo Markdown u otro BadRequest, reintenta en texto plano.
    """
    try:
        await query.edit_message_text(texto, reply_markup=reply_markup, parse_mode=parse_mode)
    except BadRequest as e:
        if "not modified" in str(e).lower():
            return
        logger.warning("edit_message_text fallo (%s); reintentando sin formato", e)
        try:
            await query.edit_message_text(texto, reply_markup=reply_markup)
        except BadRequest as e2:
            if "not modified" not in str(e2).lower():
                logger.error("edit_message_text fallo de nuevo: %s", e2)


async def _responder(message, texto, reply_markup=None, parse_mode=None):
    """reply_text que nunca rompe el flujo: si el parseo Markdown falla, reintenta en texto plano."""
    try:
        await message.reply_text(texto, reply_markup=reply_markup, parse_mode=parse_mode)
    except BadRequest as e:
        logger.warning("reply_text fallo (%s); reintentando sin formato", e)
        try:
            await message.reply_text(texto, reply_markup=reply_markup)
        except BadRequest as e2:
            logger.error("reply_text fallo de nuevo: %s", e2)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _responder(
        update.message,
        "\U0001f3b0 *HOLA PREPARADO PARA GANAR?*\nSelecciona un metodo:",
        reply_markup=teclado_principal(), parse_mode="Markdown"
    )
    return METHOD

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _responder(
        update.message,
        "Selecciona un metodo:", reply_markup=teclado_principal()
    )
    return METHOD

async def metodo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not query.data.startswith("loteria_select:"):
        context.user_data["metodo"] = query.data
    try:
        return await _atender_boton(query, context)
    except Exception as e:
        logger.error("Error en el boton %s: %s", query.data, e, exc_info=True)
        try:
            await _editar(query, "Ocurrio un error al procesar este boton. Intenta de nuevo.", reply_markup=teclado_principal())
        except Exception:
            logger.exception("No se pudo informar el error en el mensaje")
        return METHOD


async def _atender_boton(query, context: ContextTypes.DEFAULT_TYPE):
    if query.data == "super_kino":
        await _editar(query, "\U0001f3c6 Actualizando datos Kino TV...")
        try:
            n_kino = await asyncio.to_thread(actualizar_kino)
            if n_kino:
                logger.info("Kino TV: %d sorteos nuevos", n_kino)
        except Exception:
            pass
        await _editar(query, "\U0001f3c6 Generando combinaciones Super Kino TV...")
        combo1, combo2, combo3, total, f1, f2 = await asyncio.to_thread(metodo_super_kino)
        try:
            guardada = await asyncio.to_thread(guardar_prediccion_kino, combo1, combo2, combo3)
            if guardada:
                logger.info("Kino TV: prediccion de hoy guardada (1ra del dia)")
        except Exception:
            logger.exception("Kino TV: no se pudo guardar la prediccion")
        aciertos_info = None
        try:
            aciertos_info = await asyncio.to_thread(aciertos_prediccion_ayer)
        except Exception:
            logger.exception("Kino TV: error calculando aciertos de ayer")
        texto = formatear_super_kino(combo1, combo2, combo3, total, f1, f2, aciertos_info)
        await _editar(query, texto, parse_mode="Markdown", reply_markup=teclado_principal())
        return METHOD
    elif query.data == "powerball":
        await _editar(
            query,
            "POWERBALL\n*Metodo 1* usa el ultimo sorteo como base para predecir.\n*Metodo 2* es barajado aleatorio.",
            reply_markup=POWERBALL_KEYBOARD,
            parse_mode="Markdown",
        )
        return METHOD
    elif query.data in ("powerball_metodo1", "powerball_metodo2"):
        metodo = 1 if query.data == "powerball_metodo1" else 2
        base = None
        if metodo == 1:
            await _editar(query, "POWERBALL\nBuscando el ultimo sorteo...")
            try:
                await asyncio.to_thread(actualizar_powerball)
                base = await asyncio.to_thread(predecir_powerball_desde_ultimo)
            except Exception:
                logger.exception("Powerball: fallo el metodo 1")
                base = None
            if base:
                blancos, rojo = base["blancos"], base["rojo"]
            else:
                blancos, rojo = generar_powerball_metodo1()
        else:
            blancos, rojo = generar_powerball_metodo2()
        await _editar(
            query,
            formatear_powerball(blancos, rojo, metodo, base),
            parse_mode="Markdown",
            reply_markup=POWERBALL_KEYBOARD,
        )
        return METHOD
    elif query.data == "secuencias":
        await _editar(query, "Escribe el nombre de la loteria que quieres cruzar con las secuencias:\n\nEj: *La Primera Noche*, *Loteka*, *New York Tarde*, *Leidsa*, *Real*, *Gana Mas*, *Anguilla 9AM*...\n\nTambien puedes buscar por palabra clave: *primera*, *noche*, *anguilla*, *leidsa*, *quemaito*, etc.", reply_markup=ATRAS, parse_mode="Markdown")
        return LOTERIA
    elif query.data == "b2b3_menu":
        await _editar(
            query,
            "\U0001f50d *B2/B3*\nElige que resultados quieres ver:",
            reply_markup=teclado_b2b3(),
            parse_mode="Markdown",
        )
        return METHOD
    elif query.data in ("b2b3_hoy", "b2b3_ayer"):
        es_hoy = query.data == "b2b3_hoy"
        fecha = hoy_dr() if es_hoy else hoy_dr() - timedelta(days=1)
        etiqueta = "HOY" if es_hoy else "AYER"
        await _editar(
            query,
            f"\U0001f50d *B2/B3 DE {etiqueta}*\nAnalizando resultados disponibles...",
        )
        try:
            df = context.bot_data["df"]
            top, total_sorteos, total_nums = await asyncio.to_thread(
                b2b3_frecuentes_fecha, df, fecha, todos=es_hoy
            )
            b1s = set() if es_hoy else await asyncio.to_thread(b1s_de_fecha, df, fecha)
            texto = formatear_b2b3_fecha(
                top, fecha, total_sorteos, total_nums, es_hoy, b1s
            )
        except Exception as e:
            logger.error("Error en B2/B3 de %s: %s", etiqueta, e, exc_info=True)
            texto = f"Error al obtener B2/B3 de {etiqueta.lower()}. Intenta mas tarde."
        await _editar(
            query,
            texto,
            parse_mode="Markdown",
            reply_markup=teclado_b2b3(),
        )
        return METHOD
    elif query.data == "anguila":
        await _editar(query, "\U0001f41d Buscando ultimo sorteo de Anguilla de hoy...")
        try:
            df = context.bot_data["df"]
            res = await asyncio.to_thread(predecir_anguila_auto, df)
            if res is None:
                await _editar(query, "No hay sorteo de Anguilla de hoy aun.\n\nIntenta mas tarde.", reply_markup=teclado_principal())
                return METHOD
            counter_a, counter_b, b1_actual, tag_actual, tag_sig, total_a, total_b = res
            texto = formatear_anguila_auto(counter_a, counter_b, b1_actual, tag_actual, tag_sig, total_a, total_b)
        except Exception as e:
            logger.error("Error en ANGUILA: %s", e, exc_info=True)
            texto = "Error interno en ANGUILA: %s\n\nIntenta mas tarde." % str(e)
        await _editar(query, texto, parse_mode="Markdown", reply_markup=teclado_principal())
        return METHOD
    elif query.data == "super_pale":
        await _editar(query, "\U0001f9e7 Buscando B1s que salieron un dia como hoy...")
        df = context.bot_data["df"]
        contador, hoy, total = await asyncio.to_thread(super_pale_dia_como_hoy, df)
        if contador is None:
            await _editar(query, "Sin datos para un dia como hoy.", reply_markup=teclado_principal())
            return METHOD
        texto = formatear_super_pale(contador, hoy, total)
        await _editar(query, texto, parse_mode="Markdown", reply_markup=teclado_principal())
        return METHOD
    elif query.data == "loteria":
        await _editar(query, "Escribe el nombre de la loteria que quieres jugar (elige entre las 43 disponibles):\n\nEj: *La Primera Noche*, *Loteka*, *New York Tarde*, *Anguilla 9AM*, *Leidsa*, *Real*, *Gana Mas*, *Florida Tarde*, *Georgia Dia*, *Haiti Bolet 5:30 PM*, *Quemaito*\n\nTambien puedes buscar por palabra clave: *primera*, *noche*, *anguilla*, *georgia*, *haiti*, *quemaito*, etc.", reply_markup=ATRAS, parse_mode="Markdown")
        return LOTERIA
    elif query.data == "manual":
        await _editar(query, "Inserta los numeros que han salido hoy separados por espacio (ej: 12 45 83):", reply_markup=ATRAS)
        return NUMBERS
    elif query.data == "atras":
        await _editar(query, "Selecciona un metodo:", reply_markup=teclado_principal())
        return METHOD
    elif query.data.startswith("loteria_select:"):
        nombre = query.data.split(":", 1)[1]
        if context.user_data.get("metodo") == "secuencias":
            texto = await _secuencias_lotseq(nombre, context)
        else:
            df = context.bot_data["df"]
            resultado = await asyncio.to_thread(predecir_loteria_secuencia, nombre, df)
            texto = formatear_loteria(resultado, nombre)
        await _editar(query, texto, parse_mode="Markdown", reply_markup=teclado_principal())
        return METHOD
    else:
        logger.warning("callback_data sin boton asignado: %s", query.data)
        await _editar(query, "Selecciona un metodo:", reply_markup=teclado_principal())
        return METHOD

async def numeros_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    metodo = context.user_data.get("metodo")
    df = context.bot_data["df"]
    b1_a_fechas = context.bot_data["b1_a_fechas"]

    entrada = raw.replace(",", " ").replace("-", " ")
    try:
        numeros = sorted({int(x) for x in entrada.split()})
        if not all(0 <= n <= 99 for n in numeros):
            await _responder(update.message, "Solo numeros entre 0 y 99. Intenta de nuevo:", reply_markup=ATRAS)
            return NUMBERS
    except ValueError:
        await _responder(update.message, "Entrada invalida. Solo numeros separados por espacio (ej: 12 45 83):", reply_markup=ATRAS)
        return NUMBERS

    if metodo == "manual":
        texto = formatear_prediccion(numeros, b1_a_fechas, df)
    else:
        texto = "Metodo no reconocido."

    await _responder(update.message, texto, parse_mode="Markdown", reply_markup=teclado_principal())
    return METHOD

async def _secuencias_lotseq(nombre, context):
    try:
        secuencias = await asyncio.to_thread(cargar_secuencias, RUTA_SECUENCIAS)
        if not secuencias:
            return "No hay secuencias cargadas en el archivo."

        b1s_hoy = await asyncio.to_thread(scrapear_hoy)
        if not b1s_hoy:
            return "No se pudieron obtener los B1 de hoy.\n\nIntenta mas tarde."

        df = context.bot_data["df"]
        resultado = await asyncio.to_thread(predecir_loteria_secuencia, nombre, df)
        prediccion, ultimo, ultima_fecha, total = resultado
        if prediccion is None:
            return f"No hay suficientes datos historicos para {nombre}."

        cruzados = await asyncio.to_thread(cruzar_secuencias_lotseq, secuencias, b1s_hoy, prediccion)
        b1_ayer = await asyncio.to_thread(b1_ayer_loteria, nombre, df)
        return formatear_secuencias_v2(nombre, cruzados, b1_ayer, ultimo, ultima_fecha)
    except Exception as e:
        logger.error("Error en SECUENCIAS x LOTSEQ: %s", e, exc_info=True)
        return f"Error interno: {e}\n\nIntenta mas tarde."

async def loteria_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    df = context.bot_data["df"]

    matches = await asyncio.to_thread(buscar_loterias, raw, df)

    if not matches:
        await _responder(
            update.message,
            f"No encontre ninguna loteria con \"{raw}\".\n\n"
            "Ejemplos: La Primera Noche, Loteka, New York Tarde, Anguilla 9AM, LoteDom, Leidsa, Real",
            reply_markup=teclado_principal()
        )
        return METHOD

    if len(matches) == 1:
        nombre = matches[0]
        if context.user_data.get("metodo") == "secuencias":
            texto = await _secuencias_lotseq(nombre, context)
        else:
            resultado = await asyncio.to_thread(predecir_loteria_secuencia, nombre, df)
            texto = formatear_loteria(resultado, nombre)
        await _responder(update.message, texto, parse_mode="Markdown", reply_markup=teclado_principal())
        return METHOD

    # Multiple matches - show as buttons
    botones = []
    for nombre in matches[:10]:
        botones.append([InlineKeyboardButton(nombre, callback_data=f"loteria_select:{nombre}")])
    botones.append([InlineKeyboardButton("\U0001f519 Atras", callback_data="atras")])

    await _responder(
        update.message,
        f"Encontre varias loterias con \"{raw}\". Selecciona una:",
        reply_markup=InlineKeyboardMarkup(botones)
    )
    return METHOD


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _responder(update.message, "Menu principal:", reply_markup=teclado_principal())
    return METHOD

S = "│"

def formatear_prediccion(numeros, b1_a_fechas, df):
    contador, fechas, max_count, mejores_pales = predecir_b1(numeros, b1_a_fechas, df)
    hoy_set = set(numeros)
    for n in numeros:
        hoy_set.add(inverso(n))
    lineas = [f"\U0001f3b2 *Pool B1={numeros}*"]
    lineas.append(f"Fecha(s) con max coincidencias: {len(fechas)} | {max_count}/{len(numeros)}")
    if fechas:
        fechas_str = ", ".join(str(f) for f in sorted(fechas)[:5])
        lineas.append(f"Fechas: {fechas_str}")
    lineas.append("")
    if contador:
        lineas.append(f"`# {S} NUM {S} FREC {S} ACOMP`")
        lineas.append("`" + "-" * 30 + "`")
        vistos = set()
        for num_orig, count in contador.most_common(20):
            num = inverso(num_orig) if num_orig in hoy_set else num_orig
            if num in vistos or num in hoy_set:
                continue
            vistos.add(num)
            pal = ""
            if num_orig in mejores_pales:
                pn, pc = mejores_pales[num_orig]
                pal = f"+{pn}({pc})"
            lineas.append(f"`{len(vistos):<2}{S} {num:<2} {S} {count:<3} {S} {pal:<10}`")
            if len(vistos) >= 10:
                break
    else:
        lineas.append("Sin candidatos.")
    return "\n".join(lineas)

def formatear_b2b3_freq(top10):
    hoy = hoy_dr()
    lineas = [f"\U0001f50d *B2/B3 MAS FRECUENTES UN DIA COMO HOY ({hoy.day:02d})*"]
    lineas.append("B2/B3 de todos los sorteos en dias con dia del mes como hoy")
    lineas.append("(03/30 es un solo bolo)")
    lineas.append("")
    if not top10:
        lineas.append("Sin datos disponibles.")
        return "\n".join(lineas)
    lineas.append(f"`# {S} NUM {S} VECES {S}  %`")
    lineas.append("`" + "-" * 27 + "`")
    total = sum(cnt for _, cnt in top10)
    for i, (num, cnt) in enumerate(top10, 1):
        pct = cnt / total * 100 if total > 0 else 0
        inv = (num % 10) * 10 + num // 10
        par_str = f"{num:02d}/{inv:02d}"
        lineas.append(f"`{i:<2}{S} {par_str:<7}{S} {cnt:<5}{S} {pct:.0f}%`")
    lineas.append("")
    nums = [f"{n:02d}/{inv_of(n):02d}" for n, _ in top10]
    lineas.append(f"*Pool:* {', '.join(nums)}")
    return "\n".join(lineas)


def formatear_b2b3_fecha(top10, fecha, total_sorteos, total_nums, es_hoy, b1s=None):
    if es_hoy:
        titulo = f"\U0001f50d *B2/B3 QUE YA SALIERON HOY ({fecha.strftime('%d/%m/%Y')})*"
        detalle = "Solo sorteos de hoy ya publicados"
    else:
        titulo = f"\U0001f50d *B2/B3 DE AYER ({fecha.strftime('%d/%m/%Y')})*"
        detalle = "Top 10 mas repetidos (solo B2 y B3; B1 excluido)"
    lineas = [
        titulo,
        detalle,
        "03/30 se cuenta como un solo numero | el 0 (premio que no salio) no cuenta",
        f"Sorteos analizados: {total_sorteos} | B2/B3 contados: {total_nums}",
        "",
    ]
    if not top10:
        if es_hoy:
            lineas.append("Todavia no hay B2/B3 disponibles de hoy.")
        else:
            lineas.append("No hay datos de B2/B3 de ayer.")
        return "\n".join(lineas)

    lineas.append(f"`# {S} NUM {S} VECES {S}  %`")
    lineas.append("`" + "-" * 27 + "`")
    for i, (num, cnt) in enumerate(top10, 1):
        pct = cnt / total_nums * 100 if total_nums else 0
        par_str = f"{num:02d}/{inv_of(num):02d}"
        marca = "        "
        if b1s and (num in b1s or inv_of(num) in b1s):
            marca = "[salio] "
        lineas.append(f"`{i:<2}{S} {par_str:<7}{S} {marca}{cnt:<5}{S} {pct:.0f}%`")
    lineas.append("")
    nums = [f"{n:02d}/{inv_of(n):02d}" for n, _ in top10]
    lineas.append(f"*Pool:* {', '.join(nums)}")
    return "\n".join(lineas)


def inv_of(n):
    return (n % 10) * 10 + n // 10


def formatear_anguila_auto(counter_a, counter_b, b1_actual, tag_actual, tag_sig, total_a, total_b):
    lineas = [f"\U0001f41d *ANGUILA {tag_sig} (automatico)*"]
    lineas.append(f"Ultimo de hoy {tag_actual}: *{b1_actual}*\n")
    lineas.append(f"\U0001f3af *5 NUMEROS {tag_actual} -> {tag_sig} (mismo dia):*")
    if counter_a:
        for i, (num, count) in enumerate(counter_a.most_common(5), 1):
            lineas.append(f"`{i:<2}{S} {num:02d}{S} {count:<5}`")
    else:
        lineas.append("Sin historial para esta transicion.")
    lineas.append("")
    lineas.append(f"\U0001f50d *10 B1s (dias con los B1 de hoy hasta {tag_actual}):*")
    if counter_b:
        for i, (num, count) in enumerate(counter_b.most_common(10), 1):
            lineas.append(f"`{i:<2}{S} {num:02d}{S} {count:<5}`")
    else:
        lineas.append("Sin historial suficiente.")
    lineas.append("")
    lineas.append(f"A: {total_a} casos | B: {total_b} casos")
    return "\n".join(lineas)

def formatear_super_pale(contador, hoy, total):
    lineas = [f"\U0001f9e7 *SUPER PALE {hoy.day}/{hoy.month}*"]
    lineas.append("\U0001f525 *10 BOLOS MAS FRECUENTES (incluye inverso):*")
    lineas.append(f"`# {S} NUM {S} VECES`")
    lineas.append("`" + "-" * 24 + "`")
    for i, (num, count) in enumerate(contador.most_common(10), 1):
        inv = (num % 10) * 10 + num // 10
        par_str = f"{num:02d}/{inv:02d}"
        lineas.append(f"`{i:<2}{S} {par_str:<7}{S} {count}`")
    lineas.append("")
    lineas.append("\U0001f9e7 *SUPER PALE (03/30 es un solo bolo):*")
    for a, b in super_pale_pares(contador):
        ainv = (a % 10) * 10 + a // 10
        binv = (b % 10) * 10 + b // 10
        lineas.append(f"`{a:02d}/{ainv:02d}-{b:02d}/{binv:02d}`")
    return "\n".join(lineas)

def formatear_decenas(numeros):
    decenas = analizar_decenas(numeros)
    lineas = [f"\U0001f4c5 *ANALISIS POR DECENAS*"]
    lineas.append(f"B1s del dia: {sorted(numeros)}\n")
    for d in range(10):
        inicio = d * 10
        data = decenas.get(d)
        if not data:
            continue
        lineas.append(f"*DECENA {data['rango']}*")
        if data["salieron"]:
            lineas.append(f"  Salieron: {', '.join(f'{n:02d}' for n in data['salieron'])}")
        faltaron_con_inv = [n for n in data["faltaron"] if n in data["inversos"]]
        faltaron_sin_inv = [n for n in data["faltaron"] if n not in data["inversos"]]
        if faltaron_con_inv:
            for n in faltaron_con_inv:
                inv = data["inversos"][n]
                lineas.append(f"  \U0000274c {n:02d} <- salio como {inv:02d}")
        if faltaron_sin_inv:
            falt_str = ", ".join(f"{n:02d}" for n in faltaron_sin_inv)
            lineas.append(f"  \U0000274c Faltaron: {falt_str}")
        lineas.append("")
    return "\n".join(lineas)

def formatear_secuencias_v2(nombre, cruzados, b1_ayer, ultimo, ultima_fecha):
    lineas = ["\U0001f3af *SECUENCIAS x LOTSEQ*", ""]
    lineas.append(f"\U0001f3e0 *{nombre}*")
    lineas.append(f"\U0001f4c5 Ultimo B1: {ultimo:02d} ({ultima_fecha})")
    lineas.append("")

    if cruzados:
        lineas.append("\U0001f4af *B1s que coinciden (secuencias vs LOTSEQ):*")
        nums = " ".join(f"{n:02d}" for n in cruzados)
        lineas.append(f"`{nums}`")
    else:
        lineas.append("Sin coincidencias entre las secuencias (2+ aciertos hoy) y el pool LOTSEQ.")
    lineas.append("")

    if b1_ayer is not None:
        rev = transformar_reverso(b1_ayer)
        lineas.append(f"\U0001f519 *REVERSO*: B1 ayer={b1_ayer:02d} -> `{rev:02d}`  (1=6,2=7,3=8,4=9,5=0)")
    else:
        lineas.append("No hay B1 de ayer para calcular el REVERSO.")

    return "\n".join(lineas)

def formatear_atrasados(atrasados, salidos, total):
    decenas = defaultdict(list)
    for n in atrasados:
        d = n // 10
        decenas[d].append(n)
    lineas = ["\U0001f504 *ATRASADOS POR SEMANA*"]
    lineas.append(f"Total sorteos 7d: {total} | Salieron: {salidos} | Atrasados: {len(atrasados)}\n")
    for d in range(10):
        nums = decenas.get(d, [])
        if not nums:
            continue
        inicio = d * 10
        fin = inicio + 9
        lineas.append(f"`{inicio:02d}-{fin}: {', '.join(f'{n:02d}' for n in nums)}`")
    return "\n".join(lineas)

def formatear_loteria(resultado, loteria):
    prediccion, ultimo, ultima_fecha, total = resultado

    if resultado[0] is None:
        return f"\U0001f3e0 *{loteria}*\nNo hay suficientes datos historicos (minimo 2 registros)."

    lineas = [f"\U0001f3e0 *{loteria}*"]
    lineas.append(f"\U0001f4c5 Ultimo sorteo: {ultima_fecha}")
    lineas.append(f"\U0001f522 Ultimo B1: {ultimo:02d}\n")

    if not prediccion or total == 0:
        lineas.append(f"El numero {ultimo:02d} no ha vuelto a salir despues de la ultima vez.")
        return "\n".join(lineas)

    lineas.append(f"*Prediccion secuencial* (basado en {total} historico(s) de B1={ultimo:02d}):")
    lineas.append(f"`# {S} NUM {S} FREC {S}  %`")
    lineas.append("`" + "-" * 25 + "`")
    for i, (num, count) in enumerate(prediccion, 1):
        pct = count / total * 100
        lineas.append(f"`{i:<2}{S} {num:<2} {S} {count:<4}{S} {pct:.0f}%`")

    return "\n".join(lineas)


def formatear_super_kino(combo1, combo2, combo3=None, total=0, primera=None, ultima=None, aciertos_info=None):
    lineas = ["\U0001f3c6 *SUPER KINO TV*"]
    if total:
        lineas.append(f"Analisis de {total} sorteos ({primera} - {ultima})")
    else:
        lineas.append("Analisis de sorteos de Kino TV")
    lineas.append("")

    if aciertos_info:
        fecha_ayer, sorteo, detalles = aciertos_info
        sorteo_str = " ".join(f"{n:02d}" for n in sorted(sorteo))
        partes = " | ".join(f"`{nombre}`: *{aciertos}/10*" for nombre, aciertos, _c in detalles)
        lineas.append(f"*ACIERTOS DE AYER ({fecha_ayer}):*")
        lineas.append(partes)
        lineas.append(f"Sorteo ({len(sorteo)} nums): `{sorteo_str}`")
        lineas.append("")

    if combo1:
        nums1 = " ".join(f"{n:02d}" for n in combo1)
        lineas.append("*COMBINACION 1 - BALANCED:*")
        lineas.append("5 mas frecuentes de 1-40 + 5 de 41-80")
        lineas.append("`%s`" % nums1)
    else:
        lineas.append("Sin datos de Kino TV disponibles.")

    lineas.append("")

    if combo2:
        nums2 = " ".join(f"{n:02d}" for n in combo2)
        lineas.append("*COMBINACION 2 - RECIENTES 60 DIAS:*")
        lineas.append("Los 10 mas frecuentes de los ultimos 60 sorteos")
        lineas.append("`%s`" % nums2)

    lineas.append("")

    if combo3:
        nums3 = " ".join(f"{n:02d}" for n in combo3)
        lineas.append("*COMBINACION 3 - RANDOM:*")
        lineas.append("10 numeros aleatorios (1-80)")
        lineas.append("`%s`" % nums3)

    lineas.append("")
    lineas.append("*10 de 80 numeros - Sorteo: 9PM*")

    return "\n".join(lineas)


def formatear_repeticiones_hoy(repetidos, scrape):
    lineas = ["\U0001f501 *REPETIDOS HOY*"]
    lineas.append("Top 10 mas frecuentes desde 8AM hasta 6PM")
    lineas.append("(B1+B2+B3 en cualquier posicion)")
    lineas.append("")
    
    if not scrape:
        lineas.append("No hay resultados de hoy aun.")
        return "\n".join(lineas)
    
    # Mostrar cuantos resultados hay
    manana_tarde = [n for n in scrape.keys() if any(x in n for x in ['8AM', '9AM', '10AM', '11AM', '12PM', '1PM', '2PM', '3PM', '4PM', '5PM', 'Dia', 'Tarde', 'Gana'])]
    lineas.append(f"*Resultados de hoy:* {len(manana_tarde)} loterias")
    lineas.append("")
    
    if not repetidos:
        lineas.append("No hay datos disponibles aun.")
        return "\n".join(lineas)
    
    lineas.append("*TOP 10 NUMEROS (8AM - 6PM):*")
    lineas.append(f"`# {S} NUM {S} VECES {S}  %`")
    lineas.append("`" + "-" * 25 + "`")
    total = sum(cnt for _, cnt in repetidos)
    for i, (num, cnt) in enumerate(repetidos, 1):
        pct = cnt / total * 100 if total > 0 else 0
        lineas.append(f"`{i:<2}{S} {num:02d}{S} {cnt:<4}{S} {pct:.0f}%`")
    
    lineas.append("")
    nums = [f"{n:02d}" for n, _ in repetidos]
    lineas.append(f"*Pool:* {', '.join(nums)}")
    
    return "\n".join(lineas)


def formatear_repeticiones_ayer(top10, ayer):
    lineas = [f"\U0001f504 *REPETIDOS AYER*"]
    lineas.append(f"Top 10 mas frecuentes del {ayer} (B1+B2+B3)")
    lineas.append("Candidatos a repetirse HOY despues de 6PM")
    lineas.append("")
    
    if not top10:
        lineas.append("No hay datos de ayer.")
        return "\n".join(lineas)
    
    lineas.append(f"`# {S} NUM {S} VECES {S}  %`")
    lineas.append("`" + "-" * 25 + "`")
    total = sum(cnt for _, cnt in top10)
    for i, (num, cnt) in enumerate(top10, 1):
        pct = cnt / total * 100 if total > 0 else 0
        lineas.append(f"`{i:<2}{S} {num:02d}{S} {cnt:<4}{S} {pct:.0f}%`")
    
    lineas.append("")
    nums = [f"{n:02d}" for n, _ in top10]
    lineas.append(f"*Pool:* {', '.join(nums)}")
    
    return "\n".join(lineas)


def formatear_2da_3ra_ayer(top10, ayer):
    lineas = [f"\U0001f502 *2DA Y 3RA AYER*"]
    lineas.append(f"Top 10 mas frecuentes de 2da y 3ra bola del {ayer}")
    lineas.append("Solo B2 y B3 (sin B1)")
    lineas.append("")
    
    if not top10:
        lineas.append("No hay datos de ayer.")
        return "\n".join(lineas)
    
    lineas.append(f"`# {S} NUM {S} VECES {S}  %`")
    lineas.append("`" + "-" * 25 + "`")
    total = sum(cnt for _, cnt in top10)
    for i, (num, cnt) in enumerate(top10, 1):
        pct = cnt / total * 100 if total > 0 else 0
        lineas.append(f"`{i:<2}{S} {num:02d}{S} {cnt:<4}{S} {pct:.0f}%`")
    
    lineas.append("")
    nums = [f"{n:02d}" for n, _ in top10]
    lineas.append(f"*Pool:* {', '.join(nums)}")
    
    return "\n".join(lineas)


def iniciar_health_server():
    import threading
    import os
    import time
    import urllib.request
    from http.server import HTTPServer, BaseHTTPRequestHandler
    port = int(os.environ.get("PORT", 10000))
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        def log_message(self, *a):
            pass
    s = HTTPServer(("0.0.0.0", port), H)
    t = threading.Thread(target=s.serve_forever, daemon=True)
    t.start()
    print(f"Health server en puerto {port}")
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    def self_ping():
        while True:
            time.sleep(300)
            try:
                if render_url:
                    urllib.request.urlopen(render_url, timeout=10)
                else:
                    urllib.request.urlopen(f"http://localhost:{port}", timeout=5)
            except:
                pass
    threading.Thread(target=self_ping, daemon=True).start()

def main():
    import sys
    # redeploy trigger 30-jul-2026
    token = cargar_token()
    if not token:
        print("ERROR: No se encuentra el token.")
        print("Crea un archivo 'bot_token.txt' o define la variable de entorno BOT_TOKEN.")
        sys.exit(1)

    iniciar_health_server()

    print("Actualizando datos...", flush=True)
    try:
        from actualizar_datos import main as actualizar
        actualizar()
    except Exception as e:
        print(f"Advertencia al actualizar datos: {e}", flush=True)

    print("Actualizando Kino TV...", flush=True)
    try:
        n_kino = actualizar_kino()
        if n_kino:
            print(f"Kino TV: {n_kino} sorteos nuevos", flush=True)
    except Exception as e:
        print(f"Advertencia al actualizar Kino TV: {e}", flush=True)

    print("Cargando datos...", flush=True)
    try:
        df = cargar_datos()
        b1_a_fechas = construir_indices(df)
        print(f"Registros: {len(df):,}", flush=True)
        print("Precomputando cache Anguila...", flush=True)
        ang_cache, ang_dias = precomputar_cache_anguila(df)
        print(f"Cache Anguila: {len(ang_cache)} entradas", flush=True)
    except Exception as e:
        print(f"ERROR al cargar datos: {e}", flush=True)
        sys.exit(1)

    app = Application.builder().token(token).build()
    app.bot_data["df"] = df
    app.bot_data["b1_a_fechas"] = b1_a_fechas
    app.bot_data["anguila_cache"] = ang_cache
    app.bot_data["anguila_cache_dias"] = ang_dias

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start), CommandHandler("menu", menu_command), CommandHandler("cancelar", cancelar), MessageHandler(filters.TEXT & ~filters.COMMAND, start)],
        states={
            METHOD: [CallbackQueryHandler(metodo_handler), MessageHandler(filters.TEXT & ~filters.COMMAND, start)],
            NUMBERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, numeros_handler), CallbackQueryHandler(metodo_handler)],
            LOTERIA: [MessageHandler(filters.TEXT & ~filters.COMMAND, loteria_handler), CallbackQueryHandler(metodo_handler)],
        },
        fallbacks=[CommandHandler(["cancel", "cancelar"], cancelar), MessageHandler(filters.TEXT & ~filters.COMMAND, start)],
    )
    app.add_handler(conv)
    print("Bot iniciado.", flush=True)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

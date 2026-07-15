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
import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from io import StringIO
import os
import sys

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

from analisis_quinielas import cargar_datos, construir_indices, inverso, scrapear_hoy, predecir_b1, analizar, scrapear_fecha, analizar_decenas, cargar_secuencias, analizar_secuencias, predecir_anguila_siguiente, anguila_horarios_ordenados, precomputar_cache_anguila, predecir_loteria_secuencia, buscar_loterias, metodo_final, repeticiones_hoy, repeticiones_ayer, repeticiones_2da_3ra_ayer

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

_script_dir = os.path.dirname(os.path.abspath(__file__))
RUTA_SECUENCIAS = os.path.join(_script_dir, "03-10-25-05-66-00.txt")

METHOD, NUMBERS, LOTERIA = range(3)

KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("\U0001f3c6 METODO FINAL", callback_data="metodo_final")],
    [InlineKeyboardButton("\U0001f4e1 PREDICCION AUTO", callback_data="auto")],
    [InlineKeyboardButton("\U0001f3b2 PREDICCION MANUAL", callback_data="manual")],
    [InlineKeyboardButton("\U0001f50d IA ACOMPAÑANTES AUTO", callback_data="b2b3auto")],
    [InlineKeyboardButton("\U0001f511 IA ACOMPAÑANTES MANUAL", callback_data="b2b3manual")],
    [InlineKeyboardButton("\U0001f41d ANGUILA SIGUIENTE HORA", callback_data="anguila")],
    [InlineKeyboardButton("\U0001f501 REPETIDOS HOY", callback_data="repeticiones_hoy")],
    [InlineKeyboardButton("\U0001f504 REPETIDOS AYER", callback_data="repeticiones_ayer")],
    [InlineKeyboardButton("\U0001f502 2DA Y 3RA AYER", callback_data="repeticiones_2da_3ra")],
    [InlineKeyboardButton("\U0001f4c5 ANALISIS DIA ANTERIOR", callback_data="decenas")],
    [InlineKeyboardButton("\U0001f3af SECUENCIAS", callback_data="secuencias")],
    [InlineKeyboardButton("\U0001f3e0 SELECCIONAR LOTERIA", callback_data="loteria")],
])
ATRAS = InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f519 Atras", callback_data="atras")]])

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "\U0001f3b0 *HOLA PREPARADO PARA GANAR?*\nSelecciona un metodo:",
        reply_markup=KEYBOARD, parse_mode="Markdown"
    )
    return METHOD

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Selecciona un metodo:", reply_markup=KEYBOARD
    )
    return METHOD

async def metodo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["metodo"] = query.data
    if query.data == "auto":
        await query.edit_message_text("\U0001f4e1 Ejecutando metodo automatico del dia...\nScrapeando resultados de hoy...")
        pool = await asyncio.to_thread(scrapear_hoy)
        if not pool:
            await query.edit_message_text("No se pudieron obtener resultados de hoy.\n\nIntenta mas tarde o usa otro metodo.", reply_markup=KEYBOARD)
            return METHOD
        df = context.bot_data["df"]
        b1_a_fechas = context.bot_data["b1_a_fechas"]
        texto = formatear_prediccion(pool, b1_a_fechas, df)
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=KEYBOARD)
        return METHOD
    elif query.data == "decenas":
        ayer = date.today() - timedelta(days=1)
        await query.edit_message_text(f"\U0001f4c5 Buscando resultados de {ayer}...")
        pool = await asyncio.to_thread(scrapear_fecha, ayer)
        if not pool:
            await query.edit_message_text(f"No se encontraron resultados de {ayer}.\n\nIntenta con otro metodo.", reply_markup=KEYBOARD)
            return METHOD
        texto = formatear_decenas(pool)
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=KEYBOARD)
        return METHOD
    elif query.data == "metodo_final":
        await query.edit_message_text("\U0001f3c6 Ejecutando METODO FINAL...\nScrapeando Anguila + Acompanantes + Anguila Seq...")
        df = context.bot_data["df"]
        ang_cache = context.bot_data.get("anguila_cache", {})
        ang_dias = context.bot_data.get("anguila_cache_dias", {})
        b1, hora, hora_sig, pred, scrape = await asyncio.to_thread(metodo_final, df, ang_cache, ang_dias)
        texto = formatear_metodo_final(b1, hora, hora_sig, pred, scrape)
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=KEYBOARD)
        return METHOD
    elif query.data == "calientes":
        df = context.bot_data["df"]
        desde = date.today() - timedelta(days=7)
        try:
            df_filtrado = df[df["fecha"] >= desde]
        except Exception:
            df_filtrado = df
        texto = formatear_calientes(df_filtrado)
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=KEYBOARD)
        return METHOD
    elif query.data == "pares":
        df = context.bot_data["df"]
        texto = formatear_pares(df)
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=KEYBOARD)
        return METHOD
    elif query.data == "secuencias":
        await query.edit_message_text("\U0001f3af Buscando resultados de ayer y hoy...")
        ayer = date.today() - timedelta(days=1)
        pool_ayer = await asyncio.to_thread(scrapear_fecha, ayer)
        pool_hoy = await asyncio.to_thread(scrapear_hoy)
        resultados = list(set(pool_ayer + pool_hoy))
        if not resultados:
            await query.edit_message_text("No se pudieron obtener resultados.\n\nIntenta mas tarde.", reply_markup=KEYBOARD)
            return METHOD
        try:
            secuencias = await asyncio.to_thread(cargar_secuencias, RUTA_SECUENCIAS)
        except Exception as e:
            await query.edit_message_text(f"Error al cargar secuencias: {e}", reply_markup=KEYBOARD)
            return METHOD
        analisis = analizar_secuencias(secuencias, resultados)
        texto = formatear_secuencias(analisis, resultados)
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=KEYBOARD)
        return METHOD
    elif query.data == "atrasados":
        await query.edit_message_text("\U0001f504 Buscando numeros atrasados 7 dias...")
        df = context.bot_data["df"]
        atrasados, salidos, total = numeros_atrasados(df)
        texto = formatear_atrasados(atrasados, salidos, total)
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=KEYBOARD)
        return METHOD
    elif query.data == "b2b3auto":
        await query.edit_message_text("\U0001f50d Buscando ultimo B1 del dia...")
        pool = await asyncio.to_thread(scrapear_hoy)
        if pool:
            ultimo = [pool[-1]]
            df = context.bot_data["df"]
            b1_a_fechas = context.bot_data["b1_a_fechas"]
            texto = formatear_b2b3(ultimo, b1_a_fechas, df)
            await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=KEYBOARD)
            return METHOD
        await query.edit_message_text("No se pudieron obtener resultados.\n\nInserta los numeros manualmente (ej: 12 45 83):", reply_markup=ATRAS)
        return NUMBERS
    elif query.data == "b2b3manual":
        await query.edit_message_text("Inserta los numeros B1 del dia separados por espacio (ej: 12 45 83):", reply_markup=ATRAS)
        return NUMBERS
    elif query.data == "anguila":
        horas = ", ".join(anguila_horarios_ordenados())
        await query.edit_message_text(f"Ingresa el numero B1 de Anguilla y la hora (ej: 45 8AM):\n\nHorarios: {horas}", reply_markup=ATRAS)
        return NUMBERS
    elif query.data == "repeticiones_hoy":
        await query.edit_message_text("\U0001f501 Buscando resultados de hoy...")
        df = context.bot_data["df"]
        try:
            repetidos, scrape = await asyncio.to_thread(repeticiones_hoy, df)
            if not scrape:
                texto = "No se pudieron obtener resultados de hoy.\n\nIntenta mas tarde."
            else:
                texto = formatear_repeticiones_hoy(repetidos, scrape)
        except Exception as e:
            texto = "Error al obtener resultados: %s\n\nIntenta mas tarde." % str(e)
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=KEYBOARD)
        return METHOD
    elif query.data == "repeticiones_ayer":
        await query.edit_message_text("\U0001f504 Buscando top 10 de AYER...")
        df = context.bot_data["df"]
        top10, ayer = await asyncio.to_thread(repeticiones_ayer, df)
        texto = formatear_repeticiones_ayer(top10, ayer)
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=KEYBOARD)
        return METHOD
    elif query.data == "repeticiones_2da_3ra":
        await query.edit_message_text("\U0001f502 Buscando 2da y 3ra bola de AYER...")
        df = context.bot_data["df"]
        top10, ayer = await asyncio.to_thread(repeticiones_2da_3ra_ayer, df)
        texto = formatear_2da_3ra_ayer(top10, ayer)
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=KEYBOARD)
        return METHOD
    elif query.data == "loteria":
        await query.edit_message_text("Escribe el nombre de la loteria que quieres jugar (elige entre las 54 disponibles):\n\nEj: *La Primera Noche*, *Loteka*, *New York Tarde*, *Anguilla 9AM*, *Leidsa*, *Real*, *Gana Mas*, *Florida Tarde*, *Georgia Dia*, *Haiti Bolet 5:30 PM*\n\nTambien puedes buscar por palabra clave: *primera*, *noche*, *anguilla*, *georgia*, *haiti*, etc.", reply_markup=ATRAS, parse_mode="Markdown")
        return LOTERIA
    elif query.data == "manual":
        await query.edit_message_text("Inserta los numeros que han salido hoy separados por espacio (ej: 12 45 83):", reply_markup=ATRAS)
        return NUMBERS
    elif query.data == "atras":
        await query.edit_message_text("Selecciona un metodo:", reply_markup=KEYBOARD)
        return METHOD
    elif query.data and query.data.startswith("loteria_select:"):
        nombre = query.data.split(":", 1)[1]
        df = context.bot_data["df"]
        resultado = await asyncio.to_thread(predecir_loteria_secuencia, nombre, df)
        texto = formatear_loteria(resultado, nombre)
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=KEYBOARD)
        return METHOD
    else:
        await query.edit_message_text("Inserta los numeros que han salido en primera el dia de hoy (ej: 12 45 83):", reply_markup=ATRAS)
        return NUMBERS

async def numeros_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    metodo = context.user_data.get("metodo")
    df = context.bot_data["df"]
    b1_a_fechas = context.bot_data["b1_a_fechas"]

    if metodo == "anguila":
        m = re.match(r"(\d+)\s*(.*)", raw.upper().strip())
        if m:
            b1 = int(m.group(1))
            hora = m.group(2).strip().replace(" ", "")
            if hora in [str(h) for h in range(1, 13)]:
                h_num = int(hora)
                if 8 <= h_num <= 11:
                    hora += "AM"
                else:
                    hora += "PM"
            cache = context.bot_data.get("anguila_cache", {})
            dias_cache = context.bot_data.get("anguila_cache_dias", {})
            contador, sig_tag, total = predecir_anguila_siguiente(b1, hora, df, cache, dias_cache)
            texto = formatear_anguila_seq(b1, hora, contador, sig_tag, total)
        else:
            texto = "Formato invalido. Usa: numero hora (ej: 45 8AM)"
        await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=KEYBOARD)
        return METHOD

    entrada = raw.replace(",", " ").replace("-", " ")
    try:
        numeros = sorted({int(x) for x in entrada.split()})
        if not all(0 <= n <= 99 for n in numeros):
            await update.message.reply_text("Solo numeros entre 0 y 99. Intenta de nuevo:")
            return NUMBERS
    except ValueError:
        await update.message.reply_text("Entrada invalida. Solo numeros separados por espacio (ej: 12 45 83):")
        return NUMBERS

    if metodo == "manual":
        texto = formatear_prediccion(numeros, b1_a_fechas, df)
    elif metodo == "b2b3manual":
        texto = formatear_b2b3(numeros, b1_a_fechas, df)
    else:
        texto = "Metodo no reconocido."

    await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=KEYBOARD)
    return METHOD

async def loteria_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    df = context.bot_data["df"]

    matches = await asyncio.to_thread(buscar_loterias, raw, df)

    if not matches:
        await update.message.reply_text(
            f"No encontre ninguna loteria con \"{raw}\".\n\n"
            "Ejemplos: La Primera Noche, Loteka, New York Tarde, Anguilla 9AM, LoteDom, Leidsa, Real",
            reply_markup=KEYBOARD
        )
        return METHOD

    if len(matches) == 1:
        nombre = matches[0]
        resultado = await asyncio.to_thread(predecir_loteria_secuencia, nombre, df)
        texto = formatear_loteria(resultado, nombre)
        await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=KEYBOARD)
        return METHOD

    # Multiple matches - show as buttons
    botones = []
    for nombre in matches[:10]:
        botones.append([InlineKeyboardButton(nombre, callback_data=f"loteria_select:{nombre}")])
    botones.append([InlineKeyboardButton("\U0001f519 Atras", callback_data="atras")])

    await update.message.reply_text(
        f"Encontre varias loterias con \"{raw}\". Selecciona una:",
        reply_markup=InlineKeyboardMarkup(botones)
    )
    return METHOD


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Menu principal:", reply_markup=KEYBOARD)
    return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Menu principal:", reply_markup=KEYBOARD)
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
        for num_orig, count in contador.most_common(10):
            num = inverso(num_orig) if num_orig in hoy_set else num_orig
            if num in vistos or num in hoy_set:
                continue
            vistos.add(num)
            pal = ""
            if num_orig in mejores_pales:
                pn, pc = mejores_pales[num_orig]
                pal = f"+{pn}({pc})"
            lineas.append(f"`{len(vistos):<2}{S} {num:<2} {S} {count:<3} {S} {pal:<10}`")
            if len(vistos) >= 5:
                break
    else:
        lineas.append("Sin candidatos.")
    return "\n".join(lineas)

def formatear_b2b3(numeros, b1_a_fechas, df):
    contador, fechas, problemas, mejores_pares, max_count, _ = analizar(numeros, b1_a_fechas, df)
    lineas = [f"\U0001f50d *B1={numeros} - Acompanantes B2/B3*"]
    if problemas:
        lineas.append(f"Maximo coincide: {max_count}/{len(numeros)}")
        for num, motivo in problemas:
            lineas.append(f"  - {num}: {motivo}")
    lineas.append(f"Analizando {len(fechas)} fechas\n")
    if contador:
        lineas.append(f"`# {S} NUM {S} FREC {S} ACOMP`")
        lineas.append("`" + "-" * 30 + "`")
        for i, (num, count) in enumerate(contador.most_common(5), 1):
            par = ""
            if num in mejores_pares:
                pn, pc = mejores_pares[num]
                par = f"+{pn}({pc})"
            lineas.append(f"`{i:<2}{S} {num:<2} {S} {count:<3} {S} {par:<10}`")
    else:
        lineas.append("Sin acompanantes en B2/B3.")
    return "\n".join(lineas)

def formatear_anguila(numeros, df):
    ang = df[df["loteria"].str.contains("Anguilla", case=False, na=False)].copy()
    if ang.empty:
        return "No hay datos de Anguilla."
    ang["horario"] = ang["loteria"].str.replace("Anguilla", "", case=False).str.strip()
    pool = set(numeros)
    for n in numeros:
        pool.add(inverso(n))
    match = ang[ang["b1"].isin(pool)]
    if match.empty:
        return "Ninguno de esos numeros ha salido en B1 de Anguilla."
    fechas = set(match["fecha"])
    rows = ang[ang["fecha"].isin(fechas)]
    contador = Counter()
    horarios_por_num = defaultdict(set)
    for _, row in rows.iterrows():
        b1 = int(row["b1"])
        contador[b1] += 1
        horarios_por_num[b1].add(row["horario"])
    lineas = [f"\U0001f41d *Anguila B1={numeros}*"]
    lineas.append(f"{len(match)} coincidencias en {len(fechas)} dias")
    lineas.append(f"Total sorteos: {len(rows)}\n")
    lineas.append(f"`# {S} NUM {S} FREC {S} HORARIOS`")
    lineas.append("`" + "-" * 35 + "`")
    for i, (num, count) in enumerate(contador.most_common(5), 1):
        hrs = ", ".join(sorted(horarios_por_num[num])[:3])
        if len(horarios_por_num[num]) > 3:
            hrs += "..."
        lineas.append(f"`{i:<2}{S} {num:<2} {S} {count:<3} {S} {hrs:<15}`")
    return "\n".join(lineas)

def formatear_anguila_seq(b1, hora, contador, sig_tag, total_dias):
    if contador is None:
        return f"No hay suficientes datos para {b1:02d} a las {hora}.\n\n*Horarios:* {', '.join(anguila_horarios_ordenados())}"
    if not contador:
        return f"El numero {b1:02d} a las {hora} nunca se repitio en la hora siguiente ({sig_tag}) en {total_dias} dias."
    lineas = [f"\U0001f41d *Anguila {hora} -> {sig_tag}*"]
    lineas.append(f"B1={b1:02d} | {total_dias} dias historicos con esta secuencia")
    lineas.append(f"")
    lineas.append(f"`# {S} NUM {S} FREC {S}  %`")
    lineas.append("`" + "-" * 25 + "`")
    for i, (num, count) in enumerate(contador.most_common(10), 1):
        pct = count / total_dias * 100
        lineas.append(f"`{i:<2}{S} {num:<2} {S} {count:<4}{S} {pct:.0f}%`")
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

def formatear_secuencias(analisis, resultados):
    lineas = ["\U0001f3af *SECUENCIAS - TOP MATCHES*"]
    lineas.append(f"Resultados: {sorted(resultados)}\n")
    top = analisis[:5]
    for idx, item in enumerate(top, 1):
        faltan = item["faltantes"]
        if faltan:
            lineas.append(f"*SECUENCIA {idx}*")
            lineas.append(f"  \U0001f53a *FALTAN:* {', '.join(f'{n:02d}' for n in faltan)}")
            lineas.append("")
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
    for i, (num, count) in enumerate(prediccion[:10], 1):
        pct = count / total * 100
        lineas.append(f"`{i:<2}{S} {num:<2} {S} {count:<4}{S} {pct:.0f}%`")

    return "\n".join(lineas)


def formatear_metodo_final(b1, hora, hora_sig, prediccion, scrape):
    if b1 is None:
        ang_hoy = scrape if scrape else []
        lineas = ["\U0001f3c6 *METODO FINAL*"]
        if ang_hoy:
            lineas.append(f"Anguillas de hoy: {', '.join(f'{n}: {b1}' for n, b1 in ang_hoy.items() if 'anguilla' in n.lower())}")
        lineas.append("\nNo se encontro Anguila con resultado hoy.")
        lineas.append("\n*Horarios de Anguila:*")
        lineas.append(", ".join(anguila_horarios_ordenados()))
        return "\n".join(lineas)

    lineas = ["\U0001f3c6 *METODO FINAL*"]
    lineas.append(f"*Anguila {hora}* B1 = **{b1:02d}**")
    lineas.append(f"Predice para: *{hora_sig}*")
    lineas.append("")

    if prediccion:
        lineas.append("*TOP 15 COMBINADOS (Acomp + AngSeq):*")
        lineas.append(f"`# {S} NUM {S} SCORE`")
        lineas.append("`" + "-" * 20 + "`")
        for i, (num, score) in enumerate(prediccion[:15], 1):
            lineas.append(f"`{i:<2}{S} {num:02d}{S} {score}`")
        lineas.append("")
        nums = [f"{n:02d}" for n, _ in prediccion[:15]]
        lineas.append(f"*Pool:* {', '.join(nums)}")
    else:
        lineas.append("Sin predicciones disponibles.")

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
        entry_points=[CommandHandler("start", start), CommandHandler("menu", menu_command), CommandHandler("cancelar", cancel), MessageHandler(filters.TEXT & ~filters.COMMAND, start)],
        states={
            METHOD: [CallbackQueryHandler(metodo_handler), MessageHandler(filters.TEXT & ~filters.COMMAND, start)],
            NUMBERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, numeros_handler), CallbackQueryHandler(metodo_handler)],
            LOTERIA: [MessageHandler(filters.TEXT & ~filters.COMMAND, loteria_handler), CallbackQueryHandler(metodo_handler)],
        },
        fallbacks=[CommandHandler(["cancel", "cancelar"], cancel), MessageHandler(filters.TEXT & ~filters.COMMAND, start)],
    )
    app.add_handler(conv)
    print("Bot iniciado.", flush=True)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

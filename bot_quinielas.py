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
from collections import Counter, defaultdict
from datetime import date, timedelta
from io import StringIO
import os
import sys

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

from analisis_quinielas import cargar_datos, construir_indices, inverso, scrapear_hoy, predecir_b1, analizar, obtener_calientes, pares_frecuentes, scrapear_fecha, analizar_decenas, cargar_secuencias, analizar_secuencias

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

_script_dir = os.path.dirname(os.path.abspath(__file__))
RUTA_SECUENCIAS = os.path.join(_script_dir, "03-10-25-05-66-00.txt")

METHOD, NUMBERS = range(2)

KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("\U0001f4e1 PREDICCION IA DEL DIA", callback_data="auto")],
    [InlineKeyboardButton("\U0001f3b2 PREDICCION RESULTADOS EN PRIMERA", callback_data="manual")],
    [InlineKeyboardButton("\U0001f50d IA DE ACOMPAÑANTES", callback_data="b2b3")],
    [InlineKeyboardButton("\U0001f41d PREDICCION PARA ANGUILAS", callback_data="anguila")],
    [InlineKeyboardButton("\U0001f4c5 ANALISIS DIA ANTERIOR", callback_data="decenas")],
    [InlineKeyboardButton("\U0001f525 NUMEROS CALIENTES", callback_data="calientes")],
    [InlineKeyboardButton("\U0001f4ca PARES FRECUENTES", callback_data="pares")],
    [InlineKeyboardButton("\U0001f3af SECUENCIAS", callback_data="secuencias")],
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
    elif query.data == "calientes":
        await query.edit_message_text("\U0001f525 Analizando ultimos 7 dias...")
        df = context.bot_data["df"]
        desde = date.today() - timedelta(days=7)
        df_reciente = df[df["fecha"] >= desde]
        if df_reciente.empty:
            await query.edit_message_text("No hay datos de la ultima semana.\n\nIntenta con otro metodo.", reply_markup=KEYBOARD)
            return METHOD
        texto = formatear_calientes(df_reciente)
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
    elif query.data == "anguila":
        await query.edit_message_text("INGRESA LOS NUMEROS QUE HAN SALIDO EN PRIMERA EN TODAS LAS ANGUILAS EL DIA DE HOY (ej: 12 45 83):", reply_markup=ATRAS)
        return NUMBERS
    elif query.data == "atras":
        await query.edit_message_text("Selecciona un metodo:", reply_markup=KEYBOARD)
        return METHOD
    else:
        await query.edit_message_text("Inserta los numeros que han salido en primera el dia de hoy (ej: 12 45 83):", reply_markup=ATRAS)
        return NUMBERS

async def numeros_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    entrada = texto.replace(",", " ").replace("-", " ")
    try:
        numeros = sorted({int(x) for x in entrada.split()})
        if not all(0 <= n <= 99 for n in numeros):
            await update.message.reply_text("Solo numeros entre 0 y 99. Intenta de nuevo:")
            return NUMBERS
    except ValueError:
        await update.message.reply_text("Entrada invalida. Solo numeros separados por espacio (ej: 12 45 83):")
        return NUMBERS

    metodo = context.user_data.get("metodo")
    df = context.bot_data["df"]
    b1_a_fechas = context.bot_data["b1_a_fechas"]

    if metodo == "manual":
        texto = formatear_prediccion(numeros, b1_a_fechas, df)
    elif metodo == "b2b3":
        texto = formatear_b2b3(numeros, b1_a_fechas, df)
    elif metodo == "anguila":
        texto = formatear_anguila(numeros, df)
    else:
        texto = "Metodo no reconocido."

    await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=KEYBOARD)
    return METHOD

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Menu principal:", reply_markup=KEYBOARD)
    return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Menu principal:", reply_markup=KEYBOARD)
    return METHOD

S = "│"

LOTERIAS_SUG = {
    "auto": ["New Jersey Tarde", "Anguilla 12PM", "Anguilla 7PM", "La Primera Noche", "Anguilla 6PM"],
    "b2b3": ["Anguilla 12PM", "Haiti Bolet 11:30 AM", "Loteka", "New Jersey Noche", "Anguilla 8AM"],
    "anguila": ["Anguilla 10AM", "Anguilla 11AM", "Anguilla 10PM", "Anguilla 9AM", "Anguilla 2PM"],
    "decenas": ["New Jersey Tarde", "La Primera Noche", "Loteka", "Anguilla 7PM", "Haiti Bolet 11:30 AM"],
    "calientes": ["New Jersey Tarde", "La Primera Noche", "Anguilla 7PM", "Loteka", "Anguilla 6PM"],
    "pares": ["Anguilla 12PM", "New Jersey Noche", "La Primera Noche", "Anguilla 7PM", "Haiti Bolet 11:30 AM"],
    "secuencias": ["New Jersey Tarde", "Anguilla 7PM", "La Primera Noche", "Loteka", "Anguilla 6PM"],
}

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
        lineas.append(f"`# {S}   {S} NUM {S} FREC {S} ACOMP`")
        lineas.append("`" + "-" * 36 + "`")
        for i, (num, count) in enumerate(contador.most_common(10), 1):
            hoy = "\u2705" if num in hoy_set else "  "
            pal = ""
            if num in mejores_pales:
                pn, pc = mejores_pales[num]
                pal = f"+{pn}({pc})"
            lineas.append(f"`{i:<2}{S} {hoy}{S} {num:<2} {S} {count:<3} {S} {pal:<10}`")
        lineas.append("")
        lineas.append("*LOTERIAS SUGERIDAS:*")
        for l in LOTERIAS_SUG["auto"]:
            lineas.append(f"  \U0001f4cd {l}")
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
        for i, (num, count) in enumerate(contador.most_common(10), 1):
            par = ""
            if num in mejores_pares:
                pn, pc = mejores_pares[num]
                par = f"+{pn}({pc})"
            lineas.append(f"`{i:<2}{S} {num:<2} {S} {count:<3} {S} {par:<10}`")
        lineas.append("")
        lineas.append("*LOTERIAS SUGERIDAS:*")
        for l in LOTERIAS_SUG["b2b3"]:
            lineas.append(f"  \U0001f4cd {l}")
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
    for i, (num, count) in enumerate(contador.most_common(10), 1):
        hrs = ", ".join(sorted(horarios_por_num[num])[:3])
        if len(horarios_por_num[num]) > 3:
            hrs += "..."
        lineas.append(f"`{i:<2}{S} {num:<2} {S} {count:<3} {S} {hrs:<15}`")
    lineas.append("")
    lineas.append("*LOTERIAS SUGERIDAS:*")
    for l in LOTERIAS_SUG["anguila"]:
        lineas.append(f"  \U0001f4cd {l}")
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
    lineas.append("*LOTERIAS SUGERIDAS:*")
    for l in LOTERIAS_SUG["decenas"]:
        lineas.append(f"  \U0001f4cd {l}")
    return "\n".join(lineas)

def formatear_calientes(df):
    hot, cold, total = obtener_calientes(df)
    lineas = ["\U0001f525 *NUMEROS CALIENTES*"]
    lineas.append(f"Total de sorteos: {total:,}\n")
    lineas.append(f"`# {S} NUM {S} FREC {S}  %`")
    lineas.append("`" + "-" * 25 + "`")
    for i, (num, count, pct) in enumerate(hot, 1):
        lineas.append(f"`{i:<2}{S} {num:<2} {S} {count:<4}{S} {pct:.1f}%`")
    lineas.append("")
    lineas.append("\U0001f4ca *NUMEROS FRIOS*")
    lineas.append(f"`# {S} NUM {S} FREC {S}  %`")
    lineas.append("`" + "-" * 25 + "`")
    for i, (num, count, pct) in enumerate(cold, 1):
        lineas.append(f"`{i:<2}{S} {num:<2} {S} {count:<4}{S} {pct:.1f}%`")
    lineas.append("")
    lineas.append("*LOTERIAS SUGERIDAS:*")
    for l in LOTERIAS_SUG["calientes"]:
        lineas.append(f"  \U0001f4cd {l}")
    return "\n".join(lineas)

def formatear_pares(df):
    b1_b2, b1_b3 = pares_frecuentes(df)
    lineas = ["\U0001f4ca *PARES FRECUENTES*"]
    lineas.append(f"\n`B1-B2{' ' * 16}FREC`")
    lineas.append("`" + "-" * 28 + "`")
    for i, (b1, b2, freq) in enumerate(b1_b2, 1):
        lineas.append(f"`{i:<2}{S} {b1:02d}-{b2:02d}{' ' * 11}{S} {freq:<4}`")
    lineas.append(f"\n`B1-B3{' ' * 16}FREC`")
    lineas.append("`" + "-" * 28 + "`")
    for i, (b1, b3, freq) in enumerate(b1_b3, 1):
        lineas.append(f"`{i:<2}{S} {b1:02d}-{b3:02d}{' ' * 11}{S} {freq:<4}`")
    lineas.append("")
    lineas.append("*LOTERIAS SUGERIDAS:*")
    for l in LOTERIAS_SUG["pares"]:
        lineas.append(f"  \U0001f4cd {l}")
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
    lineas.append("*LOTERIAS SUGERIDAS:*")
    for l in LOTERIAS_SUG.get("secuencias", LOTERIAS_SUG["auto"]):
        lineas.append(f"  \U0001f4cd {l}")
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

    print("Cargando datos...", flush=True)
    try:
        df = cargar_datos()
        b1_a_fechas = construir_indices(df)
        print(f"Registros: {len(df):,}", flush=True)
    except Exception as e:
        print(f"ERROR al cargar datos: {e}", flush=True)
        sys.exit(1)

    app = Application.builder().token(token).build()
    app.bot_data["df"] = df
    app.bot_data["b1_a_fechas"] = b1_a_fechas

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start), CommandHandler("menu", menu_command), CommandHandler("cancelar", cancel), MessageHandler(filters.TEXT & ~filters.COMMAND, start)],
        states={
            METHOD: [CallbackQueryHandler(metodo_handler), MessageHandler(filters.TEXT & ~filters.COMMAND, start)],
            NUMBERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, numeros_handler), CallbackQueryHandler(metodo_handler)],
        },
        fallbacks=[CommandHandler(["cancel", "cancelar"], cancel), MessageHandler(filters.TEXT & ~filters.COMMAND, start)],
    )
    app.add_handler(conv)
    print("Bot iniciado.", flush=True)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

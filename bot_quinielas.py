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
from io import StringIO
import sys

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

from analisis_quinielas import cargar_datos, construir_indices, inverso, scrapear_hoy, predecir_b1, analizar

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

METHOD, NUMBERS = range(2)

KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("\U0001f4e1 Automatico del dia", callback_data="auto")],
    [InlineKeyboardButton("\U0001f3b2 Manual (pool de B1s)", callback_data="manual")],
    [InlineKeyboardButton("\U0001f50d Acompanantes B2/B3", callback_data="b2b3")],
    [InlineKeyboardButton("\U0001f41d Anguila", callback_data="anguila")],
])

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
        "\U0001f916 *Analizador de Quinielas*\n\nSelecciona un metodo:",
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
    elif query.data == "anguila":
        await query.edit_message_text("Ingresa los numeros B1 de Anguilla (ej: 12 45 83):")
        return NUMBERS
    else:
        await query.edit_message_text("Ingresa los numeros (0-99, ej: 12 45 83):")
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

def formatear_prediccion(numeros, b1_a_fechas, df):
    contador, fechas, max_count, mejores_pales = predecir_b1(numeros, b1_a_fechas, df)
    lineas = [f"\U0001f3b2 *Pool B1={numeros}*"]
    lineas.append(f"Fecha(s) con max coincidencias: {len(fechas)} | {max_count}/{len(numeros)}")
    if fechas:
        fechas_str = ", ".join(str(f) for f in sorted(fechas)[:5])
        lineas.append(f"Fechas: {fechas_str}")
    lineas.append("")
    if contador:
        lineas.append(f"`# {S} NUM {S} FREC {S} ACOMP`")
        lineas.append("`" + "-" * 30 + "`")
        for i, (num, count) in enumerate(contador.most_common(10), 1):
            pal = ""
            if num in mejores_pales:
                pn, pc = mejores_pales[num]
                pal = f"+{pn}({pc})"
            lineas.append(f"`{i:<2}{S} {num:<2} {S} {count:<3} {S} {pal:<10}`")
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
    return "\n".join(lineas)

def iniciar_health_server():
    import threading
    import os
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
        entry_points=[CommandHandler("start", start), CommandHandler("menu", menu_command), CommandHandler("cancelar", cancel)],
        states={
            METHOD: [CallbackQueryHandler(metodo_handler)],
            NUMBERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, numeros_handler)],
        },
        fallbacks=[CommandHandler(["cancel", "cancelar"], cancel)],
    )
    app.add_handler(conv)
    print("Bot iniciado.", flush=True)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

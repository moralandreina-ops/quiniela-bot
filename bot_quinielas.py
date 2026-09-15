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
from datetime import timedelta
from io import StringIO
import os
import sys

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

from analisis_quinielas import cargar_datos, construir_indices, inverso, scrapear_hoy, predecir_b1, analizar, scrapear_fecha, analizar_decenas, cargar_secuencias, analizar_secuencias, predecir_anguila_siguiente, anguila_horarios_ordenados, precomputar_cache_anguila, predecir_anguila_auto, predecir_loteria_secuencia, buscar_loterias, metodo_super_kino, repeticiones_hoy, repeticiones_ayer, repeticiones_2da_3ra_ayer, super_pale_dia_como_hoy, super_pale_pares, hoy_dr, actualizar_kino, guardar_prediccion_kino, aciertos_prediccion_ayer

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

_script_dir = os.path.dirname(os.path.abspath(__file__))
RUTA_SECUENCIAS = os.path.join(_script_dir, "03-10-25-05-66-00.txt")

METHOD, NUMBERS, LOTERIA = range(3)

# KEYBOARD: ACOMPAÑANTES removed, B2/B3 FRECUENTES added
KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("\U0001f3b2 PREDICCION MANUAL", callback_data="manual")],
    [InlineKeyboardButton("\U0001f50d B2/B3 FRECUENTES", callback_data="b2b3freq")],
    [InlineKeyboardButton("\U0001f502 2DA Y 3RA AYER", callback_data="repeticiones_2da_3ra")],
    [InlineKeyboardButton("\U0001f41d ANGUILA SIGUIENTE HORA", callback_data="anguila")],
    [InlineKeyboardButton(f"\U0001f9e7 SUPER PALE UN DIA COMO HOY ({hoy_dr().day}/{hoy_dr().month})", callback_data="super_pale")],
    [InlineKeyboardButton("\U0001f3e0 SELECCIONAR LOTERIA", callback_data="loteria")],
    [InlineKeyboardButton("\U0001f3c6 SUPER KINO", callback_data="super_kino")],
])

ATRAS = InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f519 Atras", callback_data="atras")]])
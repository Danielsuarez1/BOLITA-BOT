import os
from verificador_pago import es_pago_valido
os.makedirs("temp", exist_ok=True)
import sqlite3
import aiohttp
import re
import html
import random
import logging
import warnings
import aiosqlite
from datetime import datetime, timedelta, timezone, time as dtime
import asyncio
import unicodedata
import math
from dotenv import load_dotenv
load_dotenv()
from thefuzz import fuzz
from spellchecker import SpellChecker
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters as F    # <-- alias 'F' para usar en todo el código
)
from telegram.error import Forbidden, RetryAfter, TimedOut
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot
class SafeBot(Bot):
    async def _with_backoff(self, method, *args, **kwargs):
        while True:
            try:
                return await method(*args, **kwargs)
            except RetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)

    async def send_message(self, *args, **kwargs):
        return await self._with_backoff(super().send_message, *args, **kwargs)

    async def copy_message(self, *args, **kwargs):
        return await self._with_backoff(super().copy_message, *args, **kwargs)

    async def send_photo(self, *args, **kwargs):
        return await self._with_backoff(super().send_photo, *args, **kwargs)
import telegram
telegram.Bot = SafeBot

# Configuración de logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Variables de entorno (desde Replit o archivo .env)
TOKEN           = os.environ.get("TOKEN")
ADMIN_ID        = int(os.environ.get("ADMIN_ID"))
GRUPO_ID        = int(os.environ.get("GRUPO_ID"))
DB_SUSCRIPTORES = "suscriptores.db"
DB_PELICULAS    = "peliculas.db"
DB_STARTS       = "starts.db"
DB_TEXTOS       = "mensajes_textos.db"
DB_PAGOS        = "pagos_pendientes.db"
DB_SUGGESTIONS  = "suggestions.db"
BOT_USERNAME    = os.environ.get("BOT_USERNAME")
FUZZ_THRESHOLD  = 95
SKIP_WORDS = {"el","la","los","las","un","una","unos","unas","de","del","al","a"}

TARJETAS_PAGO = [
    "9227-0699-9529-7895",
    "9205-0699-9293-8752"
]

# —————— Configuración ——————
TMDB_API_KEY = "7215657341:AAEiWJJky0IKlF-FJD0nZnuco7s8gnnGXQ8"
TMDB_API_URL = "https://api.themoviedb.org/3/search/movie"   # <-- ¡añádelo!
DB_PELICULAS   = "peliculas.db"
SKIP_WORDS     = {"el","la","los","las","un","una","unos","unas","de","del","al","a"}

MENSAJES_NO_ENCONTRADO = [
    "🔍No encontré lo que buscas, fíjate que hayas escrito bien el nombre✍️\nTOCA EL BOTÓN DE\n➕️ SUGERIR PELÍCULA Y ENVÍA EL NOMBRE PARA QUE LA INCORPOREMOS📥 LO MÁS RÁPIDO POSIBLE⚡️\nSiempre prueba escribir el nombre de diferentes formas ejemplo:\n➖️Los Pecadores, Pecadores\n➖️Una pelicula de Minecraft, Minecraft, Una Pelicula\n➖️La casa de papel, Papel, La Casa, Casa",
    "Hmm... no encontré esa, pero hasta los cines se equivocan a veces\nTOCA EL BOTÓN DE\n➕️ SUGERIR PELÍCULA\n PARA INCORPORARLA📥 LO MÁS RÁPIDO POSIBLE⚡️\nSiempre prueba escribir el nombre de lo que buscas de diferentes formas ejemplo:\n➖️Una Pelicula de Minecraft, Minecraft\n➖️La casa de papel, Papel, La casa, Casa\n➖️Pídeme lo que quieras, Pídeme, quieras",
    "No tengo eso, pero ¿ya viste *El padrino*? Es una joya\nTOCA EL BOTÓN DE\n➕️ SUGERIR PELÍCULA\n PARA INCORPORARLA📥 LO MÁS RÁPIDO POSIBLE⚡️\nSiempre prueba escribir el nombre de lo que buscas de diferentes formas ejemplo:\n➖️Una Pelicula de Minecraft, Minecraft\n➖️La casa de papel, Papel, La casa, Casa\n➖️Pídeme lo que quieras, Pídeme, quieras",
    "Esa me suena, pero aún no está en el catálogo\nTOCA EL BOTÓN DE\n ➕️ SUGERIR PELÍCULA\n PARA INCORPORARLA📥 LO MÁS RÁPIDO POSIBLE⚡️\nSiempre prueba escribir el nombre de lo que buscas de diferentes formas ejemplo:\n➖️Una Pelicula de Minecraft, Minecraft\n➖️La casa de papel, Papel, La casa, Casa\n➖️Pídeme lo que quieras, Pídeme, quieras",
    "No encontré lo que buscas pero te tengo la solución\nTOCA EL BOTÓN DE\n ➕️ SUGERIR PELÍCULA\n PARA INCORPORARLA📥 LO MÁS RÁPIDO POSIBLE⚡️\nSiempre prueba escribir el nombre de lo que buscas de diferentes formas ejemplo:\n➖️Una Pelicula de Minecraft, Minecraft\n➖️La casa de papel, Papel, La casa, Casa\n➖️Pídeme lo que quieras, Pídeme, quieras",
    "Ni en Netflix aparece esa, bro. Intenta con otro nombre\nTOCA EL BOTÓN DE\n ➕️ SUGERIR PELÍCULA\n PARA INCORPORARLA📥 LO MÁS RÁPIDO POSIBLE⚡️\nSiempre prueba escribir el nombre de lo que buscas de diferentes formas ejemplo:\n➖️Una Pelicula de Minecraft, Minecraft\n➖️La casa de papel, Papel, La casa, Casa\n➖️Pídeme lo que quieras, Pídeme, quieras"
]

pending_referrals   = {}
pending_withdrawals = {}
pending_payments    = {}
spell = SpellChecker(language='es')
english_spell = SpellChecker(language='en')
pending_payment_types = {}

def corregir_texto(texto):
    palabras, correcciones = texto.split(), []
    for p in palabras:
        if p and p[0].isupper():
            correcciones.append(p)
        else:
            low = p.lower()
            if low in spell or low in english_spell:
                correcciones.append(p)
            else:
                corr = english_spell.correction(low)
                correcciones.append(corr if corr else p)
    return " ".join(correcciones)

async def crear_bd_sorteo_async():
    async with aiosqlite.connect("bd_sorteo.db") as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS participantes (
                user_id INTEGER PRIMARY KEY,
                username TEXT
            )
        ''')
        await conn.commit()

async def crear_tabla_usuarios():
    async with aiosqlite.connect("usuarios.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                user_id INTEGER PRIMARY KEY,
                fichas INTEGER DEFAULT 0
            )
        """)
        await db.commit()

async def crear_bd_tarjetas_asignadas_async():
    async with aiosqlite.connect(DB_PAGOS) as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS tarjetas_usuarios (
                user_id INTEGER PRIMARY KEY,
                tarjeta TEXT
            )
        ''')
        await conn.commit()

async def crear_bd_free_usage_async():
    async with aiosqlite.connect(DB_SUSCRIPTORES) as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS free_usage (
                user_id INTEGER PRIMARY KEY,
                last_used TEXT
            )
        ''')
        await conn.commit()

async def crear_bd_tarjeta_uso_async():
    async with aiosqlite.connect(DB_PAGOS) as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS tarjeta_uso (
                tarjeta TEXT PRIMARY KEY,
                clasica INTEGER DEFAULT 0,
                premium INTEGER DEFAULT 0
            )
        ''')
        await conn.commit()

async def crear_bd_suggestions_async():
    async with aiosqlite.connect(DB_SUGGESTIONS) as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS suggestions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                titulo TEXT NOT NULL,
                fecha TEXT NOT NULL
            )
        ''')
        await conn.commit()

async def crear_bd_xxx18_async():
    async with aiosqlite.connect("suscripcion_xxx18.db") as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS xxx18_subs (
                user_id INTEGER PRIMARY KEY,
                paid INTEGER DEFAULT 0,
                used INTEGER DEFAULT 0,
                expiry TEXT
            )
        """)
        await conn.commit()

async def crear_bd_mensajes_textos_async():
    async with aiosqlite.connect(DB_TEXTOS) as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS mensajes_textos(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER,
                usuario TEXT,
                texto TEXT,
                enlaces TEXT,
                fecha TEXT
            )
        ''')
        await conn.commit()

async def agregar_fichas(user_id: int, cantidad: int):
    async with aiosqlite.connect("usuarios.db") as db:
        await db.execute("INSERT OR IGNORE INTO usuarios (user_id, fichas) VALUES (?, 0)", (user_id,))
        await db.execute("UPDATE usuarios SET fichas = fichas + ? WHERE user_id = ?", (cantidad, user_id))
        await db.commit()

async def limpiar_todos_los_captions():
    async with aiosqlite.connect(DB_PELICULAS) as conn:
        cursor = await conn.execute("SELECT rowid, caption FROM peliculas")
        rows = await cursor.fetchall()

        for rowid, cap in rows:
            cap_limpio = limpiar_caption(cap)
            await conn.execute(
                "UPDATE peliculas SET caption = ? WHERE rowid = ?",
                (cap_limpio, rowid)
            )

        await conn.commit()

async def ya_probo_prueba(uid):
    async with aiosqlite.connect("suscriptores.db") as db:
        async with db.execute("SELECT prueba_gratis FROM suscriptores WHERE user_id = ?", (uid,)) as cursor:
            row = await cursor.fetchone()
            return row and row[0] == 1

async def registrar_prueba(uid):
    async with aiosqlite.connect("suscriptores.db") as db:
        # Si el usuario no existe, lo insertamos
        await db.execute("INSERT OR IGNORE INTO suscriptores (user_id) VALUES (?)", (uid,))
        await db.execute("UPDATE suscriptores SET prueba_gratis = 1 WHERE user_id = ?", (uid,))
        await db.commit()

async def agregar_fichas(user_id: int, cantidad: int):
    async with aiosqlite.connect("usuarios.db") as db:
        await db.execute("UPDATE usuarios SET fichas = fichas + ? WHERE user_id = ?", (cantidad, user_id))
        await db.commit()

async def ensure_bet(context, msg):
    uid = msg.from_user.id
    bet = context.user_data.get("bet", 1)  # Por defecto 1 ficha
    saldo = await obtener_fichas(uid)
    if bet > saldo:
        await msg.reply_text(f"❌ No tienes suficientes fichas. Saldo actual: {saldo} 🥏.")
        return None
    return bet

async def guardar_mensaje_texto(mid, usuario, texto, enlaces, fecha):
    async with aiosqlite.connect(DB_TEXTOS) as conn:
        await conn.execute(
            '''
            INSERT INTO mensajes_textos(message_id, usuario, texto, enlaces, fecha)
            VALUES (?, ?, ?, ?, ?)
            ''',
            (mid, usuario, texto, ", ".join(enlaces), fecha)
        )
        await conn.commit()
    await eliminar_duplicados_mensajes_texto()

async def responder_series(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "📺✨ ¡Vamos a encontrar tu serie! ✨📺\n\n"
        "Escribe el nombre exacto o parte de él, por ejemplo:\n"
        "• Breaking Bad\n"
        "• Peaky Blinders\n"
        "• The Last of Us\n"
        "…¡o la que tú desees! 🔍🎬"
    )
    await update.message.reply_text(texto)

async def responder_peliculas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "🎥🍿 ¡Hora de buscar tu película! 🍿🎥\n\n"
        "Escribe el título, por ejemplo:\n"
        "• Camino Equivocado\n"
        "• Destino Final\n"
        "• El Hoyo\n"
        "…¡o la que más te guste! 🔍🎞"
    )
    await update.message.reply_text(texto)

async def eliminar_duplicados_mensajes_texto():
    async with aiosqlite.connect(DB_TEXTOS) as conn:
        cursor = await conn.execute("SELECT id, texto FROM mensajes_textos")
        rows = await cursor.fetchall()
        await cursor.close()

        seen = {}
        for id_, txt in rows:
            key = normalize_text(txt)
            seen.setdefault(key, []).append(id_)

        for ids in seen.values():
            for dup in ids[1:]:
                await conn.execute("DELETE FROM mensajes_textos WHERE id = ?", (dup,))
        await conn.commit()

async def buscar_textos(q):
    corregido = corregir_texto(q)
    qn = normalize_text(corregido)
    terms = [t for t in qn.split() if t not in SKIP_WORDS]

    async with aiosqlite.connect(DB_TEXTOS) as conn:
        cursor = await conn.execute("SELECT message_id, texto FROM mensajes_textos")
        rows = await cursor.fetchall()

    exact, fuzzy = [], []
    for mid, txt in rows:
        norm_txt = normalize_text(txt)
        # 1) frase completa
        if qn in norm_txt:
            exact.append((mid, txt))
            continue
        # 2) fuzzy por término o cadena
        if any(fuzz.partial_ratio(term, norm_txt) >= 80 for term in terms) \
           or fuzz.partial_ratio(qn, norm_txt) >= 80:
            fuzzy.append((mid, txt))

    return exact if exact else fuzzy

def get_main_menu_keyboard(subscribed: bool, is_admin: bool = False):
    filas = [
        ["CubafliXXX🔥"],
        ["Referidos👥️", "Estadísticas📊"],
        ["👥COMUNIDAD🌍", "💡 EXPLICACIÓN"],
        ["🎉SORTEO SEMANAL🎉"]
    ]
    if subscribed:
        filas.insert(2, ["➕ Sugerir Película"])
    if is_admin:
        filas.append(["📢Enviar a suscriptores"])
        filas.append(["🎉REALIZAR SORTEO🎉"])
    return ReplyKeyboardMarkup(filas, resize_keyboard=True)

def get_casino_menu_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("Fichas🥏"), KeyboardButton("Juegos🎯")],
         [KeyboardButton("Depositar📥"), KeyboardButton("Retirar📤")],
         [KeyboardButton("Atrás⏮️")]],
        resize_keyboard=True
    )

# Teclado simple de Cancelar
cancel_keyboard = ReplyKeyboardMarkup(
    [["Cancelar❌️"]],
    resize_keyboard=True
)

def get_referidos_menu_keyboard():
    return ReplyKeyboardMarkup([["Balance💵"], ["Retiro⬆️"], ["Atrás ⬅️"]], resize_keyboard=True)


def get_retiro_keyboard():
    return ReplyKeyboardMarkup([["Atrás ⬅️"]], resize_keyboard=True)

def get_pago_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Suscripción Clásica⚜️", callback_data="clasica")],
        [InlineKeyboardButton("Suscripción PREMIUM💎", callback_data="premium")],
        [InlineKeyboardButton("Tipos de suscripciónℹ️", callback_data="info_suscripciones")]
    ])


async def init_databases():
    await crear_bd_suggestions_async()
    await crear_bd_peliculas_async()
    await crear_bd_mensajes_textos_async()
    await crear_bd_suscriptores_async()
    await crear_bd_pagos_async()
    await crear_bd_tarjetas_asignadas_async()
    await crear_bd_tarjeta_uso_async()
    await crear_bd_starts_async()
    await limpiar_todos_los_captions()
    await crear_bd_free_usage_async()
    await crear_tabla_usuarios()
    await crear_bd_sorteo_async()
    await crear_bd_xxx18_async()

async def asignar_tarjeta(user_id):
    async with aiosqlite.connect(DB_PAGOS) as conn:
        cursor = await conn.execute(
            "SELECT tarjeta FROM tarjetas_usuarios WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        if row:
            return row[0]
        tarjeta = random.choice(TARJETAS_PAGO)
        await conn.execute(
            "INSERT INTO tarjetas_usuarios (user_id, tarjeta) VALUES (?, ?)",
            (user_id, tarjeta)
        )
        await conn.commit()
        return tarjeta

async def tiene_pago_pendiente(user_id):
    async with aiosqlite.connect(DB_PAGOS) as conn:
        cursor = await conn.execute(
            "SELECT 1 FROM pagos_pendientes WHERE user_id = ?", 
            (user_id,)
        )
        row = await cursor.fetchone()
    return row is not None

async def guardar_pending_payment_async(user_id, username):
    async with aiosqlite.connect(DB_PAGOS) as conn:
        await conn.execute('''
            INSERT OR REPLACE INTO pagos_pendientes (user_id, username, timestamp)
            VALUES (?, ?, ?)
        ''', (user_id, username, datetime.now().isoformat()))
        await conn.commit()

async def fetch_pending_payment_async(user_id):
    async with aiosqlite.connect(DB_PAGOS) as conn:
        cursor = await conn.execute('SELECT * FROM pagos_pendientes WHERE user_id = ?', (user_id,))
        row = await cursor.fetchone()
        await cursor.close()
        return row

async def eliminar_pending_payment_async(user_id):
    async with aiosqlite.connect(DB_PAGOS) as conn:
        await conn.execute('DELETE FROM pagos_pendientes WHERE user_id = ?', (user_id,))
        await conn.commit()

async def eliminar_pago_pendiente(user_id):
    await eliminar_pending_payment_async(user_id)

async def activar_usuario(user_id):
    expiracion = (datetime.now() + timedelta(days=30)).isoformat()
    async with aiosqlite.connect(DB_SUSCRIPTORES) as conn:
        await conn.execute("""
            INSERT OR IGNORE INTO suscriptores (user_id, username, estado, fecha_expiracion)
            VALUES (?, '', 'activo', ?)
        """, (user_id, expiracion))
        await conn.execute(
            "UPDATE suscriptores SET estado = 'activo' WHERE user_id = ?",
            (user_id,)
        )
        await conn.commit()

async def usuario_activo(uid):
    async with aiosqlite.connect(DB_SUSCRIPTORES) as conn:
        cursor = await conn.execute(
            "SELECT estado FROM suscriptores WHERE user_id = ?",
            (uid,)
        )
        row = await cursor.fetchone()
        await cursor.close()
    return bool(row and row[0] == "activo")

async def handle_xxx18_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    async with aiosqlite.connect("suscripcion_xxx18.db") as conn:
        cur = await conn.execute("SELECT paid, used, expiry FROM xxx18_subs WHERE user_id = ?", (uid,))
        row = await cur.fetchone()

    if row and row[0] == 1 and row[1] == 0 and datetime.strptime(row[2], "%Y-%m-%d") >= datetime.now():
        # Ya está aprobado y puede acceder
        await xxx18_access(update, context)
    else:
        # Mostrar instrucciones de pago
        await xxx18_start(update, context)

async def suspend_expired_subscriptions(app):
    today = datetime.now().strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_SUSCRIPTORES) as conn:
        # 1) Buscamos suscripciones expiradas
        cursor = await conn.execute(
            "SELECT user_id FROM suscriptores WHERE fecha_expiracion < ?",
            (today,)
        )
        rows = await cursor.fetchall()
        expired = [row[0] for row in rows]

        for uid in expired:
            n1 = await contar_referidos(uid)

            if n1 >= 5:
                # --- RENOVACIÓN GRATIS + RESET DE REFERIDOS ---
                new_exp = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
                await conn.execute(
                    "UPDATE suscriptores SET fecha_expiracion = ?, estado = 'activo' WHERE user_id = ?",
                    (new_exp, uid)
                )
                await conn.execute(
                    "UPDATE suscriptores SET referrer = NULL WHERE referrer = ?",
                    (uid,)
                )
                await conn.commit()

                try:
                    await app.bot.send_message(
                        chat_id=uid,
                        text=(
                            f"🎉¡Felicidades! Has alcanzado 5 referidos👤 de Nivel 1\n"
                            f"Tu suscripción se ha renovado🔁 GRATIS hasta el {new_exp}"
                        )
                    )
                except:
                    pass

            else:
                # --- SUSPENSIÓN NORMAL: no tocamos referidos, solo cambiamos estado ---
                await conn.execute(
                    "UPDATE suscriptores SET estado = 'suspendido' WHERE user_id = ?",
                    (uid,)
                )
                await conn.commit()
                try:
                    await app.bot.send_message(chat_id=uid, text="Su suscripción ha sido suspendida por expiración.")
                except:
                    pass

async def can_use_free_video(user_id):
    async with aiosqlite.connect(DB_SUSCRIPTORES) as conn:
        cursor = await conn.execute(
            "SELECT last_used FROM free_usage WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
    if not row:
        return True
    last = datetime.fromisoformat(row[0])
    return datetime.now() - last >= timedelta(seconds=30)

async def xxx18_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    texto = (
        "<b>🔹️Todo el p0rno que quieras de por vida por solo 500cup💵</b>\n\n"
        "Tarjeta: <code>9227-0699-9529-7895</code>\n"
        "Número a confirmar: <code>59420036</code>\n\n"
        "Resto del mundo🌎\n"
        "Criptomoneda🔰: <b>10 USDT TRC20</b>\n"
        "Dirección: <code>TNzbrvNzXvX355erbUGbgMNxCiUogR4r33</code>\n\n"
        "Cuando termines mándame la captura de pantalla📷 de la transferencia\nSi deseas cancelar el pago manda el comando /cancelar_pago"
    )
    context.user_data["awaiting_xxx18"] = True
    await update.message.reply_text(
        texto,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

# 2) Define un nuevo handler para /cancelar_pago:
async def cancelar_pagoxxx18(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.pop("awaiting_xxx18", None):
        await update.message.reply_text(
            "✅ Pago +18 cancelado.\nPresiona /start para volver al menú principal.",
            reply_markup=get_main_menu_keyboard(await esta_suscrito(update.effective_user.id))
        )
    else:
        await update.message.reply_text("No tienes ningún pago en curso.")

async def record_free_usage(user_id):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_SUSCRIPTORES) as conn:
        await conn.execute(
            "INSERT OR REPLACE INTO free_usage (user_id, last_used) VALUES (?, ?)",
            (user_id, now)
        )
        await conn.commit()

async def obtener_fichas(user_id: int) -> int:
    """
    Devuelve el número de fichas 🥏 que tiene el usuario.
    """
    async with aiosqlite.connect(DB_SUSCRIPTORES) as conn:
        cursor = await conn.execute(
            "SELECT fichas FROM suscriptores WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
    return row[0] if row else 0

# —————— Función auxiliar para descontar fichas ——————
async def descontar_fichas(user_id: int, cantidad: int):
    async with aiosqlite.connect(DB_SUSCRIPTORES) as conn:
        await conn.execute(
            "UPDATE suscriptores SET fichas = fichas - ? WHERE user_id = ?",
            (cantidad, user_id)
        )
        await conn.commit()

async def esta_suscrito(uid):
    async with aiosqlite.connect(DB_SUSCRIPTORES) as conn:
        cursor = await conn.execute(
            "SELECT fecha_expiracion, estado FROM suscriptores WHERE user_id = ?",
            (uid,)
        )
        r = await cursor.fetchone()

    if r and r[0] and r[1] == 'activo':
        return datetime.strptime(r[0], "%Y-%m-%d") >= datetime.now()
    return False

# —————— Función de broadcast en background ——————
async def _broadcast_all_starts(application, photo_id: str, caption: str):
    enviados, errores = 0, 0
    # Leemos todos los /start
    async with aiosqlite.connect(DB_STARTS) as conn:
        cursor = await conn.execute("SELECT user_id FROM starts")
        rows = await cursor.fetchall()

    for i, (uid,) in enumerate(rows):
        try:
            await application.bot.send_photo(chat_id=uid, photo=photo_id, caption=caption)
            enviados += 1
        except Forbidden:
            errores += 1
        except BadRequest as e:
            errores += 1
            logging.warning(f"[broadcast] BadRequest para {uid}: {e}")
        except Exception as e:
            errores += 1
            logging.exception(f"[broadcast] Error enviando a {uid}: {e}")

        if (i + 1) % 3 == 0:
            await asyncio.sleep(1)

    # Opcional: notificar al admin cuando termine
    await application.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"✅ Broadcast terminado: {enviados} éxitos, {errores} errores."
    )

async def activar_suscripcion(user_id, premium=False):
    fecha_expiracion = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_SUSCRIPTORES) as conn:
        cursor = await conn.execute("SELECT user_id FROM suscriptores WHERE user_id = ?", (user_id,))
        existe = await cursor.fetchone()
        await cursor.close()

        if existe:
            await conn.execute(
                "UPDATE suscriptores SET estado='activo', fecha_expiracion=?, premium=? WHERE user_id=?",
                (fecha_expiracion, int(premium), user_id)
            )
        else:
            await conn.execute(
                "INSERT INTO suscriptores (user_id, fecha_expiracion, premium, estado) VALUES (?, ?, ?, 'activo')",
                (user_id, fecha_expiracion, int(premium))
            )
        await conn.commit()

async def es_premium(user_id):
    async with aiosqlite.connect(DB_SUSCRIPTORES) as conn:
        cursor = await conn.execute(
            "SELECT premium FROM suscriptores WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        await cursor.close()
    return row and row[0] == 1

async def xxx18_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    # 1) Verifica suscripción...
    async with aiosqlite.connect("suscripcion_xxx18.db") as conn:
        cur = await conn.execute("SELECT paid, used, expiry FROM xxx18_subs WHERE user_id = ?", (uid,))
        row = await cur.fetchone()

    if not row or row[0] == 0:
        return await update.message.reply_text("❌ No tienes activa la suscripción especial +18.")
    if row[1] == 1:
        return await update.message.reply_text("❗ Ya usaste tu acceso. Debes volver a pagar para renovarlo.")
    if datetime.strptime(row[2], "%Y-%m-%d") < datetime.now():
        return await update.message.reply_text("⚠️ Tu suscripción especial ha expirado. Renueva tu acceso realizando el pago nuevamente.")

    # 2) Marcar como usado inmediatamente
    async with aiosqlite.connect("suscripcion_xxx18.db") as conn:
        await conn.execute("UPDATE xxx18_subs SET used = 1 WHERE user_id = ?", (uid,))
        await conn.commit()

    # 3) Enviar mensaje con botón protegido
    invite_url = "https://t.me/+fNPFrPX12AU4ZDFh"
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔞 Entrar a CUBAFLIX +18", url=invite_url)
    ]])
    msg = await update.message.reply_text(
        "Aquí tienes tu acceso único✅️\nEste mensaje se autodestruirá🚫 en:\n1 minuto🕜",
        reply_markup=kb,
        protect_content=True
    )

    # 4) Autodestruir el mensaje después de 10 segundos
    await asyncio.sleep(60)
    try:
        await context.bot.delete_message(
            chat_id=msg.chat_id,
            message_id=msg.message_id
        )
    except:
        pass

async def agregar_suscriptor(uid: int,
                             username: str,
                             ref: int | None = None,
                             premium: bool = False,
                             dias: int = 30,
                             periodo: str = "mensual"):
    """
    Crea o actualiza un suscriptor.
    - dias: 30 o 365
    - periodo: 'mensual' o 'anual'
    """
    exp = (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_SUSCRIPTORES) as conn:
        if ref is None:
            await conn.execute('''
                INSERT OR REPLACE INTO suscriptores
                  (user_id, username, fecha_expiracion, balance, referrer, estado, premium, periodo)
                VALUES (?, ?, ?, COALESCE((SELECT balance FROM suscriptores WHERE user_id = ?),0),
                        NULL, 'activo', ?, ?)
            ''', (uid, username, exp, uid, int(premium), periodo))
        else:
            await conn.execute('''
                INSERT OR REPLACE INTO suscriptores
                  (user_id, username, fecha_expiracion, balance, referrer, estado, premium, periodo)
                VALUES (?, ?, ?, COALESCE((SELECT balance FROM suscriptores WHERE user_id = ?),0),
                        ?, 'activo', ?, ?)
            ''', (uid, username, exp, uid, ref, int(premium), periodo))
        await conn.commit()

async def actualizar_balance(refid, amt):
    async with aiosqlite.connect(DB_SUSCRIPTORES) as conn:
        await conn.execute('''
            UPDATE suscriptores
            SET balance = balance + ?
            WHERE user_id = ?
        ''', (amt, refid))
        await conn.commit()

async def contar_referidos(uid):
    async with aiosqlite.connect(DB_SUSCRIPTORES) as conn:
        cursor = await conn.execute(
            "SELECT COUNT() FROM suscriptores WHERE referrer = ?",
            (uid,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

async def contar_referidos_nivel2(uid):
    async with aiosqlite.connect(DB_SUSCRIPTORES) as conn:
        cursor = await conn.execute(
            """
            SELECT COUNT() FROM suscriptores
            WHERE referrer IN (
                SELECT user_id FROM suscriptores WHERE referrer = ?
            )
            """,
            (uid,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

async def obtener_balance(uid):
    async with aiosqlite.connect(DB_SUSCRIPTORES) as conn:
        cursor = await conn.execute(
            "SELECT balance FROM suscriptores WHERE user_id = ?",
            (uid,)
        )
        row = await cursor.fetchone()
        await cursor.close()
    return row[0] if row else 0

async def restar_balance(uid, amt):
    async with aiosqlite.connect(DB_SUSCRIPTORES) as conn:
        await conn.execute(
            "UPDATE suscriptores SET balance = balance - ? WHERE user_id = ?",
            (amt, uid)
        )
        await conn.commit()


async def guardar_pelicula(mid, cap):
    async with aiosqlite.connect(DB_PELICULAS) as conn:
        # 1) Inserta en la tabla normal y guarda el cursor
        cur = await conn.execute(
            'INSERT INTO peliculas(message_id, caption) VALUES (?, ?)',
            (mid, cap)
        )
        await conn.commit()
        # 2) Obtiene el rowid que SQLite acaba de crear
        rowid = cur.lastrowid

        # 3) Actualiza el índice FTS con ese mismo registro
        await conn.execute(
            "INSERT INTO peliculas_fts(peliculas_fts, rowid, caption) "
            "VALUES('insert', ?, ?)",
            (rowid, cap)
        )
        await conn.commit()

def limpiar_caption(texto):
    # 1) Elimina @usuarios
    texto = re.sub(r'@\w+', '', texto)

    # 2) Elimina enlaces tipo t.me o http(s)
    texto = re.sub(r'http\S+', '', texto)
    texto = re.sub(r't\.me\S+', '', texto)

    # 3) Elimina hashtags
    texto = re.sub(r'#\w+', '', texto)

    # 4) Elimina emojis
    emoji_pattern = re.compile(
        "["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # símbolos & pictogramas
        u"\U0001F680-\U0001F6FF"  # transporte y mapas
        u"\U0001F1E0-\U0001F1FF"  # flags
        u"\U00002700-\U000027BF"  # otros símbolos
        u"\U0001F900-\U0001F9FF"  # símbolos extra
        u"\U00002600-\U000026FF"  # misceláneos
        u"\U00002B00-\U00002BFF"
        "]+", flags=re.UNICODE)
    texto = emoji_pattern.sub(r'', texto)

    # 5) Limpia espacios múltiples pero sin borrar saltos de línea
    texto = re.sub(r'[ \t]+', ' ', texto)

    # 6) Divide en líneas limpias
    lineas = [linea.strip() for linea in texto.strip().splitlines() if linea.strip()]

    # 7) Conserva solo la primera línea o primera + segunda
    if len(lineas) >= 2:
        texto_final = f"{lineas[0]} {lineas[1]}"
    else:
        texto_final = lineas[0] if lineas else BOT_USERNAME

    return texto_final.strip()

# —————— Configuración ——————
TMDB_API_KEY     = "7215657341:AAEiWJJky0IKlF-FJD0nZnuco7s8gnnGXQ8"   # tu token/API real
TMDB_API_URL     = "https://api.themoviedb.org/3/search/movie"
DB_PELICULAS     = "peliculas.db"
SKIP_WORDS       = {"el","la","los","las","un","una","unos","unas","de","del","al","a"}
FALLBACK_THRESHOLD = 50  # umbral de ruido

def normalize_text(texto: str) -> str:
    txt = unicodedata.normalize('NFD', texto).encode('ascii','ignore').decode().lower()
    txt = re.sub(r'[^\w\s]', ' ', txt)
    return re.sub(r'\s+', ' ', txt).strip()

async def fetch_api_titles(query: str) -> list[str]:
    params = {"api_key": TMDB_API_KEY, "query": query, "language": "es-ES", "page": 1}
    async with aiohttp.ClientSession() as session:
        async with session.get(TMDB_API_URL, params=params) as resp:
            data = await resp.json()
    return [item["title"] for item in data.get("results", [])]

async def search_in_db(titles: list[str]) -> list[tuple[int,str]]:
    matches = []
    async with aiosqlite.connect(DB_PELICULAS) as conn:
        rows = await (await conn.execute("SELECT message_id, caption FROM peliculas")).fetchall()
    for mid, cap in rows:
        norm_cap = normalize_text(cap)
        for title in titles:
            if normalize_text(title) in norm_cap:
                matches.append((mid, cap))
                break
    return matches

async def buscar_peliculas(q: str) -> list[tuple[int, str]]:
    qn = normalize_text(q)
    terms = [t for t in qn.split() if t not in SKIP_WORDS]

    # 1) Cargamos todos los registros de la DB
    async with aiosqlite.connect(DB_PELICULAS) as conn:
        rows = await (await conn.execute("SELECT message_id, caption FROM peliculas")).fetchall()

    # 2) Búsqueda exacta sobre el texto normalizado
    exact = [(m, c) for m, c in rows if qn in normalize_text(c)]
    if exact:
        return exact

    # 3) Búsqueda por todos los términos
    filtered = [
        (m, c) for m, c in rows
        if all(t in normalize_text(c) for t in terms)
    ]
    if filtered:
        return filtered

    # 4) Búsqueda FTS… si tienes configurada la tabla peliculas_fts
    if terms:
        search_terms = " ".join(terms)
        async with aiosqlite.connect(DB_PELICULAS) as conn:
            cur = await conn.execute(
                """SELECT p.message_id, p.caption
                   FROM peliculas_fts f
                   JOIN peliculas p ON p.rowid = f.rowid
                  WHERE f.caption MATCH ?
                  ORDER BY bm25(peliculas_fts)
                  LIMIT 10;""",
                (search_terms,)
            )
            fts_hits = await cur.fetchall()
        if fts_hits:
            return fts_hits

    # 5) Fallback a TMDB
    api_titles = await fetch_api_titles(q)
    if api_titles:
        hits = []
        for title in api_titles:
            norm_title = normalize_text(title)
            for m, c in rows:
                if norm_title in normalize_text(c):
                    hits.append((m, c))
                    break
        if hits:
            return hits

    # 6) Si no hay nada, devolvemos lista vacía
    return []

def build_search_results_message(res, page):
    ps, total = 10, math.ceil(len(res) / 10)
    header = f"Página {page+1} de {total}"
    start = page * ps
    lines = [header]
    for i, (mid, txt) in enumerate(res[start:start + ps], start=start + 1):
        lines.append(f"{i}- {limpiar_caption(txt)}")
    return "\n".join(lines)


def build_search_results_keyboard(res, page):
    ps, start = 10, page * 10
    btns = [InlineKeyboardButton(str(i), callback_data=f"seleccionar{i-1}")
            for i in range(start + 1, min(start + ps, len(res)) + 1)]
    row1, row2 = btns[:5], btns[5:]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"page_{page-1}"))
    if (page + 1) * ps < len(res):
        nav.append(InlineKeyboardButton("➡️", callback_data=f"page_{page+1}"))
    return InlineKeyboardMarkup([row1] + ([row2] if row2 else []) + ([nav] if nav else []))


async def send_search_results_page(update, context, page):
    rs = context.user_data.get('search_results', [])
    print(f"🔔 send_search_results_page: página={page}, resultados={len(rs)}")
    if not rs: return
    text = build_search_results_message(rs, page)
    kb = build_search_results_keyboard(rs, page)
    if update.callback_query:
        await update.callback_query.edit_message_text(text=text, reply_markup=kb)
    else:
        await update.message.reply_text(text=text, reply_markup=kb)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.message.from_user

    # —————— Detectamos si es admin ——————
    is_admin = (u.id == ADMIN_ID)

    # —————— Registrar /start en la tabla starts ——————
    async with aiosqlite.connect(DB_STARTS) as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO starts (user_id, fecha) VALUES (?, ?)",
            (u.id, datetime.now().isoformat())
        )
        await conn.commit()

    # —————— Capturar referidos si viene con ?start=ref_xxx ——————
    if context.args and context.args[0].startswith("ref_"):
        try:
            pending_referrals[u.id] = int(context.args[0].split("_")[1])
        except:
            pass

    nombre = u.first_name or "usuario"
    if not await esta_suscrito(u.id):
        # Usuario no suscrito: mostrar suscripciones y menú inicial
        await update.message.reply_text(
            text=(
                f"<b>Hola👋</b> {nombre}\n\n💎<b>Bienvenido</b> a👑 <a href=\"https://t.me/{BOT_USERNAME[1:]}\"><b>CUBAFLIX™</b></a>👑\n"
                "Tu puerta a <b>miles</b> de <b>Películas🎥 y Series🎞 en español🇪🇸</b>, todo <b>dentro</b> de <b>Telegram</b>\n\n"
                "🔍Solo dime el <b>nombre</b> del título que quieres\n⬇️Lo <b>descargas</b> o lo <b>vez👀</b> al instante⚡️\n"
                "🎁¡Y el <b>primer</b> video es <b>GRATIS!</b>\n"
                "<b>⚡️Actualizamos todos los días</b> con <b>+100 títulos nuevos</b>\n\n"
                "🔹️<b>Elige tu plan mensual🗓</b> y empieza a <b>disfrutar YA:</b>"
            ),
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=get_pago_keyboard()
        )
    else:
        # Usuario suscrito: menú principal con búsqueda
        await update.message.reply_text(
            f"Hola👋 {nombre}, disfruta de nuestro bot🤖\n"
            "🔍Para buscar cualquier película o serie solo dime su nombre✍️",
            reply_markup=get_main_menu_keyboard(True, is_admin)
        )

async def handle_deposit_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cantidad = context.user_data.pop('pending_fichas', None)
    if not cantidad:
        return

    user_id = update.message.from_user.id  # <- Esto es lo que faltaba

    # Enviar mensaje al usuario confirmando
    await update.message.reply_text(
        "🔹️En un instante se le validará la compra de sus Fichas🥏\nEspere por favor...",
        reply_markup=get_casino_menu_keyboard()
    )

    # Reenviar la foto al admin con los botones de aceptar/rechazar
    foto = update.message.photo[-1].file_id
    botones = InlineKeyboardMarkup([
        [InlineKeyboardButton("Aceptar depósito✅️", callback_data=f"deposito_aceptar_{user_id}_{cantidad}")],
        [InlineKeyboardButton("Rechazar depósito❌️", callback_data=f"deposito_rechazar_{user_id}_{cantidad}")]
    ])
    caption = (
        f"📥 *Nuevo depósito de fichas*\n"
        f"Usuario: @{update.message.from_user.username or update.message.from_user.id}\n"
        f"Cantidad: {cantidad} Fichas🥏\n"
        f"Debe pagar: {cantidad*10} cup💵"
    )

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=foto,
        caption=caption,
        parse_mode="Markdown",
        reply_markup=botones
    )

async def handle_buttons(update, context):
    query = update.callback_query
    await query.answer()
    d = query.data  # <-- corregido: usamos 'data' en lugar de 'd'

# —————— Acceso único a CUBAFLIX +18 ——————
    if d == "access_xxx18":
        uid = query.from_user.id

        # Verifica si ya usó el acceso
        async with aiosqlite.connect("suscripcion_xxx18.db") as conn:
            cur = await conn.execute("SELECT used FROM xxx18_subs WHERE user_id = ?", (uid,))
            row = await cur.fetchone()

        if not row or row[0] == 1:
            await query.answer("Este acceso ya fue usado.", show_alert=True)
            return

        # Marcar como usado
        async with aiosqlite.connect("suscripcion_xxx18.db") as conn:
            await conn.execute("UPDATE xxx18_subs SET used = 1 WHERE user_id = ?", (uid,))
            await conn.commit()

        # Borra el mensaje con el botón callback original
        await context.bot.delete_message(
            chat_id=query.message.chat_id,
            message_id=query.message.message_id
        )

        # Envía directamente el enlace al grupo como botón
        invite_url = "https://t.me/+fNPFrPX12AU4ZDFh"
        await context.bot.send_message(
            chat_id=uid,
            text="✅ Acceso concedido. Únete ahora:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Entrar a CUBAFLIX +18 🔞", url=invite_url)
            ]])
        )
        return

# —————— Aceptar o rechazar comprobante +18 ——————
    if d.startswith("aceptar_xxx18_") and query.from_user.id == ADMIN_ID:
        uid = int(d.split("_")[2])
        expiry = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

        async with aiosqlite.connect("suscripcion_xxx18.db") as conn:
            await conn.execute(
                "INSERT OR REPLACE INTO xxx18_subs (user_id, paid, used, expiry) VALUES (?, 1, 0, ?)",
                (uid, expiry)
            )
            await conn.commit()

        # Edita el mensaje original del admin
        await query.message.edit_caption(
            caption=f"ID: `{uid}`\n✅ Pago aceptado",
            parse_mode="Markdown"
        )

        # Notificar al usuario
        await context.bot.send_message(
            chat_id=uid,
            text="Su suscripción especial ha sido aceptada✅️\nVuelve a tocar el botón para acceder al servicio👇"
        )
        return

    if d.startswith("rechazar_xxx18_") and query.from_user.id == ADMIN_ID:
        uid = int(d.split("_")[2])

        async with aiosqlite.connect("suscripcion_xxx18.db") as conn:
            await conn.execute("DELETE FROM xxx18_subs WHERE user_id = ?", (uid,))
            await conn.commit()

        # Edita el mensaje original del admin
        await query.message.edit_caption(
            caption=f"ID: `{uid}`\n❌ Pago rechazado",
            parse_mode="Markdown"
        )

        # Notificar al usuario
        await context.bot.send_message(
            chat_id=uid,
            text="Su suscripción especial fue rechazada.❌"
        )
        return

    # Callback del botón "🎉PARTICIPA EN EL SORTEO🎉"
    if d == "participar_sorteo":
        user = query.from_user
        uid = user.id
        username = user.username or user.first_name

        if not await esta_suscrito(uid):
            await context.bot.send_message(
                chat_id=uid,
                text="✋️No eres suscriptor del bot\n🔹️Para participar activa tu suscripción mensual🔹️",
                reply_markup=get_pago_keyboard()
            )
            return

        async with aiosqlite.connect("bd_sorteo.db") as conn:
            await conn.execute(
                "INSERT OR IGNORE INTO participantes (user_id, username) VALUES (?, ?)",
                (uid, username)
            )
            await conn.commit()

        await context.bot.send_message(
            chat_id=uid,
            text="🎉LISTO🎉\n🔹️Ya estás participando en el sorteo de la semana🔹️"
        )
        return

# info_suscripciones: mostrar tipos y precios sin anual
    if d == "info_suscripciones":
        texto = (
            "*👇Tipos de suscripción👇*\n\n"
            "*Suscripción Clásica⚜️*:\n"
            "  • Buscar y ver contenido✅️\n"
            "  • *No* guardar ni reenviar❌️\n\n"
            "*Suscripción PREMIUM💎*:\n"
            "  • *Buscar🔍* contenido✅️\n"
            "  • *Ver👀* contenido✅️\n"
            "  • *Guardar*⬇️  contenido en galería✅️\n  • *Reenviar*↪️ contenido✅️\n\n"
            "*👇Precios👇*\n"
            "*Clásica⚜️*: *200* CUP 💵 / *300* Saldo📱/ *1* USDT TRC20🔰\n\n"
            "*PREMIUM💎*: *300* CUP 💵 / *400* Saldo📱/ *2* USDT TRC20🔰\n\n"
            "*Envía tu captura📷 de pago para activar tu plan*"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Suscripción Clásica⚜️", callback_data="clasica")],
            [InlineKeyboardButton("Suscripción PREMIUM💎", callback_data="premium")],
        ])
        return await query.edit_message_text(
            text=texto,
            parse_mode="Markdown",
            reply_markup=keyboard
        )

# Bloque que inicia el flujo de pago de suscripciones
    elif d in {"clasica", "premium", "suscripcion_clasica_anual", "suscripcion_premium_anual"}:
        # Importa al inicio del archivo:
        # from datetime import datetime, timedelta

        # 1) Guardamos que iniciamos el flujo de pago
        context.user_data["awaiting_payment"] = d
        # 2) Registramos el tipo exacto de suscripción
        context.user_data["tipo_pago"]        = d
        # 3) Fijamos un plazo para enviar el comprobante (10 minutos)
        context.user_data["payment_deadline"] = datetime.now() + timedelta(minutes=30)

# MENSAJE DE PAGO OPTIMIZADO PARA CLÁSICA Y PREMIUM (USANDO HTML)
        tipo         = "SUSCRIPCIÓN CLÁSICA⚜️" if "clasica" in d else "SUSCRIPCIÓN PREMIUM💎"
        cup_precio   = 200 if "clasica" in d else 300
        movil_precio = 300 if "clasica" in d else 400
        usdt_precio  = 1   if "clasica" in d else 2
        tarjeta      = "9227-0699-9529-7895"
        numero_saldo = "59420036"

        mensaje = (
            f"⚜️ Activa tu <b>{tipo}</b> y\n<b>🌟DESBLOQUEA TODO EL CONTENIDO🌟</b>\n\n"
            "<b>🎬 PELÍCULAS, SERIES🎞 Y ESTRENOS🔥</b>\nSin límites por <b>30 días</b>\n\n"
            "<b>Elige cómo pagar:</b>\n\n"
            "1️⃣ <b>Transferencia Bancaria</b>💳\n"
            f"   • <b>Tarjeta</b>: <code>{tarjeta}</code>\n"
            f"   • <b>Confirma</b>: <code>{numero_saldo}</code>\n"
            f"   • Monto: <b>{cup_precio} CUP</b>\n\n"
            "2️⃣ <b>Saldo Móvil</b>📱\n"
            f"   • <b>Número</b>: <code>{numero_saldo}</code>\n"
            f"   • <b>Monto</b>: <b>{movil_precio} CUP</b>\n\n"
            "3️⃣ <b>Cripto (USDT - TRC20)</b>💰\n"
            "   • <b>Dirección</b>: <code>TNzbrvNzXvX355erbUGbgMNxCiUogR4r33</code>\n"
            f"   • Monto: <b>{usdt_precio} USDT</b>\n\n"
            "<b>Envía una captura clara del pago para activar tu cuenta.</b>\n\n"
            "<b>¿Tienes dudas?</b> Escríbeme @Zpromo1 o presiona /cancelar❌️"
        )
        await query.edit_message_text(mensaje, parse_mode="HTML")

        # Edita el mensaje con las instrucciones
        await query.edit_message_text(text=mensaje, parse_mode="HTML")

# Confirmación del admin tras pagar al ganador
    elif d.startswith("pago_realizado_") and query.from_user.id == ADMIN_ID:
        uid_str = data.split("_")[2]
        uid = int(uid_str)

        # 1. Notificar al ganador
        await context.bot.send_message(
            chat_id=uid,
            text="✅ Ya se realizó tu pago del sorteo semanal\n¡Gracias por participar!"
        )

        # 2. Avisar a todos los usuarios registrados en starts.db
        ganador_id, ganador_username = context.bot_data.get("ganador_sorteo", (uid, "Ganador"))

        texto = (
            f"🏆 Ganador del sorteo de esta semana:\n"
            f"Nombre: {ganador_username}\n"
            f"Usuario: @{ganador_username if '@' not in ganador_username else ganador_username}\n\n"
            "🔹️Participa en el sorteo de esta nueva semana🔹️"
        )
        botones = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎉PARTICIPA EN EL SORTEO🎉", callback_data="participar_sorteo")]
        ])

        async with aiosqlite.connect(DB_START) as conn:
            cursor = await conn.execute("SELECT user_id FROM starts")
            usuarios = await cursor.fetchall()

        for (otro_uid,) in usuarios:
            try:
                await context.bot.send_message(
                    chat_id=otro_uid,
                    text=texto,
                    reply_markup=botones
                )
            except:
                continue

        # 3. Limpiar participantes del sorteo
        async with aiosqlite.connect("bd_sorteo.db") as conn:
            await conn.execute("DELETE FROM participantes")
            await conn.commit()

        await query.answer("Sorteo finalizado y todos fueron notificados.", show_alert=True)
        return

# Botón exclusivo del admin: "🎉REALIZAR SORTEO🎉"
    elif d == "realizar_sorteo" and query.from_user.id == ADMIN_ID:
        async with aiosqlite.connect("bd_sorteo.db") as conn:
            cursor = await conn.execute("SELECT user_id, username FROM participantes")
            participantes = await cursor.fetchall()

        if not participantes:
            return await query.answer("No hay participantes esta semana.", show_alert=True)

        ganador_id, ganador_username = random.choice(participantes)

        await context.bot.send_message(
            chat_id=ganador_id,
            text="🎉¡Felicidades! Has ganado el sorteo semanal de CUBAFLIX👑\n\n"
                 "Envíame tu número y tu tarjeta en un solo mensaje para recibir tu premio✅"
        )

        botones = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Ya hice el pago", callback_data=f"pago_realizado_{ganador_id}")]
        ])

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"👑 Ganador: {ganador_username}\nID: {ganador_id}\n\n"
                 "Cuando pagues, toca el botón:",
            reply_markup=botones
        )

        # Guardar al ganador en context
        context.bot_data["ganador_sorteo"] = (ganador_id, ganador_username)

        return

    # 4) Paginación de resultados de búsqueda
    elif d.startswith("page_"):
        page = int(d.split("_")[1])
        await send_search_results_page(update, context, page)
        return
    # seleccion directa
    elif d.startswith("seleccionar"):
        uid = query.from_user.id
        try:
            # si está suscrito, enviamos el video normalmente
            if await esta_suscrito(uid):
                idx = int(d.replace("seleccionar", ""))
                mid, txt = context.user_data.get("search_results", [])[idx]
                caption = f"{limpiar_caption(txt)} {BOT_USERNAME}"

                is_premium = await es_premium(uid)
                await context.bot.copy_message(
                    chat_id=uid,
                    from_chat_id=GRUPO_ID,
                    message_id=mid,
                    caption=caption,
                    protect_content=not is_premium
                )
                return

            # si no está suscrito, pero no ha usado la prueba gratuita
            if not await ya_probo_prueba(uid):
                idx = int(d.replace("seleccionar", ""))
                mid, txt = context.user_data.get("search_results", [])[idx]
                caption = f"{limpiar_caption(txt)} {BOT_USERNAME}"

                await context.bot.copy_message(
                    chat_id=uid,
                    from_chat_id=GRUPO_ID,
                    message_id=mid,
                    caption=caption,
                    protect_content=True
                )
                await registrar_prueba(uid)
                await query.answer("Este video fue enviado como prueba gratuita.")
                print(f"Usuario {uid} recibió su prueba gratuita")
                return

            # si no está suscrito y ya usó la prueba
            await query.answer()
            await context.bot.send_message(
                chat_id=uid,
                text="👋 ¡Tu prueba gratuita ha finalizado!\n\n🍕 Por menos de lo que cuesta una pizza al mes\n🎥 Accede a TODO nuestro catálogo sin límites\n⭐️ Contenido ILIMITADO y actualizaciones diarias\n\n✅️Activa tu suscripción ahora y sigue disfrutando»",
                reply_markup=get_pago_keyboard()
            )

        except (IndexError, TypeError):
            await query.answer("Selección inválida, por favor intenta de nuevo.")
        except Exception as e:
            print(f"Error al manejar selección: {e}")

    # 6) Confirmar transferencia (“Listo”)
    elif d.startswith("listo_"):
        tid = int(d.split("_")[1])
        bal = await obtener_balance(tid)
        await restar_balance(tid, bal)
        await query.edit_message_text("Transferencia Realizada✅️")
        await context.bot.send_message(tid, "Transferencia Realizada✅️")
        return
    # 7) Cualquier otro callback queda fuera

# —————— Procesar Retiro de Fichas ——————
    elif d.startswith("procesar_retiro_"):
        # callback_data == "procesar_retiro_<user_id>_<monto>"
        _, _, payload = d.partition("procesar_retiro_")
        user_id_str, monto_str = payload.split("_", 1)
        user_id = int(user_id_str)
        monto = int(monto_str)
        equivalente = monto * 9  # recalculamos el equivalente en cup

        # 1) Editar el mensaje original del admin para confirmar el procesamiento
        await query.edit_message_text(
            f"✅ Retiro procesado:\n"
            f"Usuario: `{user_id}`\n"
            f"Fichas retiradas: *{monto}* 🥏 (equivale a *{equivalente}cup💵*)",
            parse_mode="Markdown"
        )

        # 2) Notificar al usuario que su retiro se procesó
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"🎉 Tu retiro de *{monto}* fichas (equivale a *{equivalente}cup💵*) ha sido procesado ✅\n"
                "Sigue así crack, maquina, fiera, jefe, tifón, numero 1, figura, mostro, mastodonte, toro, furia, ciclón, tornado, artista, fenómeno, campeón, maestro "
            ),
            parse_mode="Markdown"
        )

        return

async def handle_payment_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    # —————— Flujo de depósito de fichas ——————
    if data.startswith("deposito_aceptar_") or data.startswith("deposito_rechazar_"):
        # formato: deposito_{acción}_{user_id}_{cantidad}
        _, acción, user_id_str, cantidad_str = data.split("_")
        user_id = int(user_id_str)
        cantidad = int(cantidad_str)

        if acción == "aceptar":
            # Aumentar fichas en la base de datos de suscriptores
            async with aiosqlite.connect(DB_SUSCRIPTORES) as conn:
                await conn.execute(
                    "UPDATE suscriptores SET fichas = fichas + ? WHERE user_id = ?",
                    (cantidad, user_id)
                )
                await conn.commit()

            # Modificar mensaje en admin
            await query.edit_message_caption("✅ Depósito aprobado correctamente.")
            # Notificar al usuario
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ Tu depósito de {cantidad} Fichas🥏 ha sido aprobado y ya está disponible en tu cuenta.",
                reply_markup=get_casino_menu_keyboard()
            )
        else:
            # Depósito rechazado
            await query.edit_message_caption("❌ Depósito rechazado.")
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ Tu depósito fue rechazado. Por favor verifica tu comprobante y vuelve a intentarlo.",
                reply_markup=get_casino_menu_keyboard()
            )
        return

# —————— Flujo de suscripciones (clásica/premium) ——————
    if data.startswith("rechazar_"):
        user_id = int(data.split("_", 1)[1])
        # Rechazar comprobante de suscripción
        await eliminar_pending_payment_async(user_id)
        pending_payments.pop(user_id, None)
        # Editar caption manteniendo sólo el ID y el estado de rechazo
        new_caption = f"ID: `{user_id}`\n\n❌ Pago rechazado"
        await query.edit_message_caption(caption=new_caption, parse_mode="Markdown")
        await context.bot.send_message(
            chat_id=user_id,
            text="Tu pago fue rechazado❌\nRevisa si la imagen fue clara\nPresiona /start y vuelve a intentarlo🔁"
        )
        return

# AUTO-PROMPT: enviar y borrar mensaje de búsqueda tras aprobación de pago
    elif data.startswith("aceptar_"):
        # Asume al comienzo del módulo: from datetime import datetime, timedelta
        user_id = int(data.split("_", 1)[1])

        # 1) Leemos tipo de pago
        async with aiosqlite.connect(DB_PAGOS) as conn:
            cursor = await conn.execute(
                "SELECT tipo_pago FROM pagos_pendientes WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
        tipo_pago_db = row[0] if row else "clasica"

        # 2) Distinguimos premium y días
        es_premium_flag = tipo_pago_db in ("premium", "suscripcion_premium_anual")
        dias = 365 if "anual" in tipo_pago_db else 30

        # 3) Eliminamos el pago pendiente
        await eliminar_pending_payment_async(user_id)
        pending_payments.pop(user_id, None)
        pending_payment_types.pop(user_id, None)

        # 4) Registro de uso de tarjeta
        tarjeta = await asignar_tarjeta(user_id)
        async with aiosqlite.connect(DB_PAGOS) as conn2:
            await conn2.execute(
                "INSERT OR IGNORE INTO tarjeta_uso (tarjeta) VALUES (?)",
                (tarjeta,)
            )
            field = "premium" if es_premium_flag else "clasica"
            await conn2.execute(
                f"UPDATE tarjeta_uso SET {field} = {field} + 1 WHERE tarjeta = ?",
                (tarjeta,)
            )
            await conn2.commit()

        # 5) Activamos al suscriptor con días y periodo correctos
        referidor_directo = pending_referrals.pop(user_id, None)
        username = pending_payments.pop(user_id, "") or ""
        username = f"@{username}" if username else ""
        await agregar_suscriptor(
            uid=user_id,
            username=username,
            ref=referidor_directo,
            premium=es_premium_flag,
            dias=dias,
            periodo=("anual" if dias == 365 else "mensual")
        )

        # 6) Aviso al admin de aprobación
        new_caption = f"ID: `{user_id}`\n\n✅ Pago aprobado"
        await query.edit_message_caption(caption=new_caption, parse_mode="Markdown")

        # 7) Notificación al usuario con fecha real
        fecha_exp = (datetime.now() + timedelta(days=dias)).strftime("%d/%m/%Y")
        await context.bot.send_message(
            chat_id=user_id,
            text=f"¡Tu pago fue aprobado!✅\nCuenta activa🟢 hasta el {fecha_exp}"
        )
        await context.bot.send_message(
            chat_id=user_id,
            text="✅ ¡Listo! Ya puedes buscar🔍 o sugerir películas y series:",
            reply_markup=get_main_menu_keyboard(True, False)
        )

        # 8) Enviar prompt de búsqueda y programar su eliminación tras 5s
        msg_prompt = await context.bot.send_message(
            chat_id=user_id,
            text="Escribe el nombre de la película o serie que desees✍️",
            reply_markup=get_main_menu_keyboard(True, False)
        )
        context.application.create_task(
            _auto_delete_prompt(
                context.application.bot,
                msg_prompt.chat_id,
                msg_prompt.message_id
            )
        )

        # 9) Recompensas por referidos
        if referidor_directo is not None:
            # 1) Leemos el periodo del referidor directo
            async with aiosqlite.connect(DB_SUSCRIPTORES) as conn:
                cur = await conn.execute(
                    "SELECT periodo FROM suscriptores WHERE user_id = ?",
                    (referidor_directo,)
                )
                row = await cur.fetchone()

            # 2) Recompensa según su tipo de suscripción
            recompensa = 50 if row and row[0] == "anual" else 50

            # 3) Aplicamos la recompensa al referido directo
            await actualizar_balance(referidor_directo, recompensa)
            await context.bot.send_message(
                chat_id=referidor_directo,
                text=f"✅️¡Un nuevo usuario se ha suscrito mediante tu enlace!\n+{recompensa}cup💵"
            )

            # 4) Revisamos si el referido directo tiene un "abuelo" (referidor de nivel 2)
            async with aiosqlite.connect(DB_SUSCRIPTORES) as conn3:
                cur2 = await conn3.execute(
                    "SELECT referrer FROM suscriptores WHERE user_id = ?",
                    (referidor_directo,)
                )
                fila = await cur2.fetchone()

            # 5) Si existe, le damos su recompensa de nivel 2
            if fila and fila[0] is not None:
                abuelo = fila[0]
                await actualizar_balance(abuelo, 25)
                await context.bot.send_message(
                    chat_id=abuelo,
                    text="✅️¡Tu referido de nivel 1 consiguió un nuevo suscriptor!\n+25cup💵"
                )
        return

async def aceptar_clasico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("No tienes permisos para ejecutar este comando.")

    if not context.args:
        return await update.message.reply_text("Por favor, proporciona el ID de usuario. Ejemplo: /aceptarclasico 5429072186")

    try:
        user_id = int(context.args[0])  # Obtén el ID del usuario
        # Activar suscripción "Clásica" para este usuario
        await activar_suscripcion(user_id, premium=False)
        await update.message.reply_text(f"Usuario {user_id} suscrito correctamente a la suscripción Clásica.")
    except ValueError:
        await update.message.reply_text("El ID proporcionado no es válido. Asegúrate de usar un ID numérico.")

async def aceptar_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("No tienes permisos para ejecutar este comando.")

    if not context.args:
        return await update.message.reply_text("Por favor, proporciona el ID de usuario. Ejemplo: /aceptarpremium 5429072186")

    try:
        user_id = int(context.args[0])  # Obtén el ID del usuario
        # Activar suscripción "Premium" para este usuario
        await activar_suscripcion(user_id, premium=True)
        await update.message.reply_text(f"Usuario {user_id} suscrito correctamente a la suscripción Premium.")
    except ValueError:
        await update.message.reply_text("El ID proporcionado no es válido. Asegúrate de usar un ID numérico.")

async def cancel_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.pop('awaiting_payment', None):
        # Esperamos el booleano de la suscripción
        suscrito = await esta_suscrito(update.message.from_user.id)
        return await update.message.reply_text(
            "Pago Cancelado\nPresiona /start si deseas disfrutar del servicio ilimitado de películas🎥 y series🎞",
            reply_markup=get_main_menu_keyboard(suscrito)
        )

async def dinero(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await enviar_reporte_tarjetas(context.application)

async def enviar_reporte_tarjetas(app):
    # 1) Leemos uso de tarjetas de forma asíncrona
    async with aiosqlite.connect(DB_PAGOS) as conn:
        cursor = await conn.execute(
            "SELECT tarjeta, clasica, premium FROM tarjeta_uso"
        )
        rows = await cursor.fetchall()

    if not rows:
        return

    # 2) Calculamos subtotales y total
    total = 0
    lines = ["Entrada de Dinero💵:"]
    for tarjeta, clasica, premium in rows:
        subtotal = (clasica * 200) + (premium * 300)
        total += subtotal
        lines.append(f"{tarjeta}: {subtotal}cup💵")
    lines.append(f"\nTotal💵: {total}cup")

    # 3) Enviamos reporte al admin
    await app.bot.send_message(
        chat_id=ADMIN_ID,
        text="\n".join(lines)
    )

async def limpiar_contadores(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Sólo el admin puede usarlo
    if update.effective_user.id != ADMIN_ID:
        return

    # 1) Reseteamos todos los usos a 0
    async with aiosqlite.connect(DB_PAGOS) as conn:
        await conn.execute("UPDATE tarjeta_uso SET clasica = 0, premium = 0")
        await conn.commit()

        # 2) Leemos de nuevo para armar el reporte
        cursor = await conn.execute("SELECT tarjeta, clasica, premium FROM tarjeta_uso")
        rows = await cursor.fetchall()

    # 3) Construimos el texto de respuesta
    total = 0
    lines = ["Entrada de Dinero💵:"]
    for tarjeta, clasica, premium in rows:
        subtotal = clasica * 200 + premium * 300
        total += subtotal
        lines.append(f"{tarjeta}: {subtotal}cup💵")
    lines.append(f"\nTotal💵: {total}cup")

    # 4) Enviamos el reporte al chat donde se invocó el comando
    await update.message.reply_text("\n".join(lines))

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # —————— Caso pago +18 previo ——————
    if context.user_data.get("awaiting_xxx18"):
        await handle_xxx18_payment_proof(update, context)
        return

    # —————— Caso broadcast de portadas ——————
    if context.user_data.get('awaiting_broadcast') and update.message.from_user.id == ADMIN_ID:
        photo_id = update.message.photo[-1].file_id
        caption = update.message.caption or ""

        # Encolamos el broadcast en segundo plano
        context.application.create_task(
            _broadcast_all_starts(context.application, photo_id, caption)
        )

        # Respuesta inmediata al admin
        await update.message.reply_text(
            "✅ Broadcast encolado y en curso en segundo plano. "
            "Te avisaré cuando termine."
        )
        context.user_data.pop('awaiting_broadcast', None)
        return

    # —————— Caso pago pendiente ——————
    if context.user_data.get('awaiting_payment'):
        await handle_payment_proof(update, context)
        return

    # —————— Caso depósito de fichas ——————
    if context.user_data.get('pending_fichas'):
        await handle_deposit_proof(update, context)
        return

    # —————— Resto de fotos no esperadas ——————
    await update.message.reply_text(
        "Lamentablemente perdí❌️ la conexión a internet📶 en el momento en que mandó el comprobante de pago🖼\n"
        "Presione /start\n"
        "Vuelva a presionar el botón de la suscripción deseada\n"
        "Vuelva a enviar la captura de pantalla de la transferencia para ahora sí mandársela al admin"
    )

async def handle_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import os
    from verificador_pago import es_pago_valido

    # 1) Verificar que estamos esperando pago
    awaiting = context.user_data.get("awaiting_payment")
    if not awaiting:
        return

    now = datetime.now()
    deadline = context.user_data.get("payment_deadline")

    # 2) Comprobar expiración
    if deadline and now > deadline:
        await update.message.reply_text(
            "⏰ El tiempo para enviar tu comprobante expiró. "
            "Vuelve a tocar el botón de suscripción para reiniciar el proceso."
        )
        context.user_data.pop("awaiting_payment", None)
        context.user_data.pop("payment_deadline", None)
        context.user_data.pop("tipo_pago", None)
        return

    user = update.message.from_user
    uid = user.id

    # 3) Evitar duplicados en la BD
    has_pending = await tiene_pago_pendiente(uid)
    if has_pending:
        await update.message.reply_text(
            "Ya enviaste un comprobante de pago📷\nEspera✋️ a que el administrador lo revise."
        )
        return

    # 4) Descargar imagen temporalmente
    foto = update.message.photo[-1]
    archivo = await foto.get_file()
    local_path = f"temp/{uid}.jpg"
    await archivo.download_to_drive(local_path)

    # 6) Borrar imagen local
    try:
        os.remove(local_path)
    except:
        pass

# …tras descargar la foto y antes de notificar al admin…
    photo_id = update.message.photo[-1].file_id
    tipo     = context.user_data.get("tipo_pago", "clasica")
    timestamp = datetime.now().isoformat()

    async with aiosqlite.connect(DB_PAGOS) as conn:
        await conn.execute('''
            INSERT OR REPLACE INTO pagos_pendientes
                (user_id, username, timestamp, photo_id, sent, tipo_pago)
            VALUES (?, ?, ?, ?, 0, ?)
        ''', (
            uid,
            update.message.from_user.username or "",
            timestamp,
            photo_id,
            tipo
        ))
        await conn.commit()

    # …ahora continúa el envío al admin…

    # 9) Enviar comprobante al admin
    # Ajustamos nombre y monto según tipo
    if tipo == "premium":
        tipo_visible = "PREMIUM💎"
        nombre_visible = "Suscripción PREMIUM💎"
        monto = 300
    elif tipo == "clasica":
        tipo_visible = "Clásica⚜️"
        nombre_visible = "Suscripción Clásica⚜️"
        monto = 200
    elif tipo == "suscripcion_clasica_anual":
        tipo_visible = "Clásica Anual⚜️ (Ahorra 17%)"
        nombre_visible = "Suscripción Clásica Anual⚜️"
        monto = 1000
    else:  # suscripcion_premium_anual
        tipo_visible = "PREMIUM Anual💎 (Ahorra 17%)"
        nombre_visible = "Suscripción PREMIUM Anual💎"
        monto = 2000

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("Aceptar✅️", callback_data=f"aceptar_{uid}")],
        [InlineKeyboardButton("Rechazar❌️", callback_data=f"rechazar_{uid}")]
    ])
    caption = (
        f"📸 *Comprobante de pago recibido*\n"
        f"Usuario: @{user.username or uid}\n"
        f"ID: `{uid}`\n"
        f"Tipo de suscripción: {tipo_visible}\n"
        f"Monto: *{monto}cup💵*\n\n"
        f"*{nombre_visible}*"
    )
    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo_id,
        caption=caption,
        reply_markup=buttons,
        parse_mode="Markdown"
    )

    async with aiosqlite.connect(DB_PAGOS) as conn3:
        await conn3.execute(
            "UPDATE pagos_pendientes SET sent = 1 WHERE user_id = ?",
            (uid,)
        )
        await conn3.commit()

    # 10) Confirmación al usuario
    await update.message.reply_text(
        "Tu pago se está verificando🔍\nEspera que el administrador lo valide..."
    )

    # 11) Limpiar estado
    context.user_data.pop("awaiting_payment", None)
    context.user_data.pop("payment_deadline", None)
    context.user_data.pop("tipo_pago", None)

async def handle_xxx18_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Flujo para procesar la foto de pago de CUBAFLIX +18.
    """
    # 1) Verificamos que esperábamos este comprobante
    if not context.user_data.get("awaiting_xxx18"):
        return

    uid = update.message.from_user.id

    # 2) Mensaje al usuario
    await update.message.reply_text("🔍 Comprobante de pago +18 recibido. Espera validación del admin…")

    # 3) Enviamos la foto al admin con botones de aceptar/rechazar
    foto_id = update.message.photo[-1].file_id
    botones = InlineKeyboardMarkup([
        [InlineKeyboardButton("Aceptar suscripción +18✅", callback_data=f"aceptar_xxx18_{uid}")],
        [InlineKeyboardButton("Rechazar suscripción +18❌", callback_data=f"rechazar_xxx18_{uid}")]
    ])
    caption = (
        f"📸 *Comprobante +18 recibido*\n"
        f"Usuario: @{update.message.from_user.username or uid}\n"
        f"ID: `{uid}`\n"
        "Servicio: CUBAFLIXXX🔥"
    )
    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=foto_id,
        caption=caption,
        reply_markup=botones,
        parse_mode="Markdown"
    )

    # 4) Limpiamos el estado de espera
    context.user_data.pop("awaiting_xxx18", None)

async def procesar_pago_automatico(user_id: int, aprobado: bool, context: ContextTypes.DEFAULT_TYPE, tipo: str = "clasica"):

    # Enviar mensaje al admin
    mensaje_admin = f"✅ Pago de {user_id} {'APROBADO' if aprobado else 'RECHAZADO'} automáticamente por IA.\n"
    mensaje_admin += f"Tipo: {'PREMIUM💎' if tipo=='premium' else 'CLÁSICA⚜️'}\n"
    mensaje_admin += f"Monto: *{300 if tipo=='premium' else 200} CUP*"

    await context.bot.send_message(chat_id=ADMIN_ID, text=mensaje_admin, parse_mode="Markdown")

    if aprobado:
        await activar_suscripcion(user_id, tipo, context)

        # Calcular fecha de expiración (30 días)
        fecha_expira = datetime.now() + timedelta(days=30)
        dia = fecha_expira.day
        meses = {
            "January": "enero", "February": "febrero", "March": "marzo",
            "April": "abril", "May": "mayo", "June": "junio",
            "July": "julio", "August": "agosto", "September": "septiembre",
            "October": "octubre", "November": "noviembre", "December": "diciembre"
        }
        mes_en = fecha_expira.strftime("%B")
        mes = meses.get(mes_en, mes_en)

        await context.bot.send_message(
            chat_id=user_id,
            text=(
                "✅ Tu suscripción ha sido aprobada automáticamente por la IA🧠\nDisfruta de todo el contenido sin límites🎥.\n"
                f"Suscripción válida hasta el {dia} de {mes}."
            )
        )
    else:
        await eliminar_pending_payment_async(user_id)
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Tu comprobante fue rechazado automáticamente por la IA🧠\nRevisa los datos👀\nPresiona /start y vuelve a hacer el proceso de pago🔁"
        )

def contiene_emoji(texto):
    emoji_regex = re.compile(
        "[\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F700-\U0001F77F"
        "\U0001F780-\U0001F7FF"
        "\U0001F800-\U0001F8FF"
        "\U0001F900-\U0001F9FF"
        "\U0001FA00-\U0001FA6F"
        "\U0001FA70-\U0001FAFF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE
    )
    return bool(emoji_regex.search(texto))

async def sugerir_pelicula(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Activamos el modo sugerencia
    context.user_data['awaiting_sugerencia'] = True
    # Teclado con botón de volver
    back_kb = ReplyKeyboardMarkup([["Atrás ⬅️"]], resize_keyboard=True)
    return await update.message.reply_text(
        "👋 Aquí puedes mandar✍️ el nombre de la Película🎥 o Serie🎞 que no encontraste.\n"
        "Se buscará🔍 en TMDB y si existe✅️, quedará registrada para subirla al bot en cuanto se pueda\n"
        "Asegúrate de escribir el nombre exacto👌 y vuelve a buscarla en el bot mañana✅️",
        reply_markup=back_kb
    )

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg   = update.message
    texto = msg.text.strip() if msg.text else ""
    uid   = msg.from_user.id

# —————— Guardar Apuesta Elegida ——————
    # Sólo tratamos dígitos como apuesta si estamos en un juego activo
    if texto.isdigit() and context.user_data.get("game"):
        apuesta = int(texto)
        saldo   = await obtener_fichas(uid)
        if apuesta <= 0 or apuesta > saldo:
            return await msg.reply_text("❌ Apuesta inválida o saldo insuficiente.")
        context.user_data["bet"] = apuesta
        return await msg.reply_text(
            f"✅ Apuesta fijada en {apuesta} Fichas🥏.\n¡Elige un juego para comenzar!",
            reply_markup=menu_juegos()
        )

    # —————— Submenú de Casino🎲 ——————
    if texto == "Casino🎲":
        context.user_data["ultimo_menu"] = "casino"
        return await msg.reply_text(
            "🎲 Bienvenido al Casino, elige una opción:",
            reply_markup=get_casino_menu_keyboard()
        )

    # —————— 1) Flujo VIEJO de suscripción (awaiting_payment) ——————
    if context.user_data.get('awaiting_payment'):
        if texto.lower() == "/cancelar":
            context.user_data.pop('awaiting_payment', None)
            suscrito = await esta_suscrito(msg.from_user.id)
            return await msg.reply_text(
                "Pago Cancelado",
                reply_markup=get_main_menu_keyboard(suscrito)
            )
        return await msg.reply_text("❌Solo se aceptan imágenes📷 como comprobante\n🔹️Presiona 👉 /cancelar si quieres salir del modo de pago🔹️\n🔹️O /start si quieres cambiar el tipo de suscripción🔹️")

    # —————— 2) Flujo NUEVO de depósito de fichas ——————

    # 2.0) Cancelar y volver al submenú de Casino
    if texto == "Cancelar❌️" and (context.user_data.get('awaiting_deposit') or context.user_data.get('pending_fichas')):
        context.user_data.pop('awaiting_deposit', None)
        context.user_data.pop('pending_fichas', None)
        return await msg.reply_text(
            "👋Hola de nuevo, prueba tu suerte🍀 con nuestros fantásticos juegos🕹\nPronto añadiremos nuevos juegos🎲",
            reply_markup=get_casino_menu_keyboard()
        )

    # 2.1) Usuario pulsa "Depositar📥"
    if texto == "Depositar📥":
        context.user_data['awaiting_deposit'] = True
        return await msg.reply_text(
            "🔹️Cada Ficha🥏 cuesta 10cup💵\n"
            "🔹️El mínimo de Fichas🥏 a comprar es de 👉5 Fichas🥏👈, no hay límite máximo♾️\n\n"
            "🔹️Primero escribe el número de Fichas🥏 que deseas comprar🔹️",
            reply_markup=cancel_keyboard
        )

    # 2.2) Usuario escribe cantidad de fichas
    if context.user_data.get('awaiting_deposit'):
        if not texto.isdigit():
            return await msg.reply_text(
                "✋️Escribe solamente el número de Fichas🥏 que deseas comprar✋️",
                reply_markup=cancel_keyboard
            )
        cantidad = int(texto)
        if cantidad < 5:
            return await msg.reply_text(
                "✋️El mínimo a comprar son 5 Fichas🥏",
                reply_markup=cancel_keyboard
            )
        # Cantidad válida → preparamos comprobante
        context.user_data.pop('awaiting_deposit')
        context.user_data['pending_fichas'] = cantidad
        amount = cantidad * 10
        return await msg.reply_text(
            f"Para comprar {cantidad} Fichas🥏\n"
            f"Envía *{amount}cup💵* a la siguiente tarjeta💳:\n"
            "Banco🏦: Bandec\n"
            "Tarjeta💳: `9227-0699-9529-7895`\n"
            "Número a confirmar📲: `59420036`\n\n"
            "Envía la captura📷 de pantalla de la transferencia para validar la compra:",
            parse_mode="Markdown",
            reply_markup=cancel_keyboard
        )

    # 2.4) Si manda otra cosa esperando la foto
    if context.user_data.get('pending_fichas'):
        return await msg.reply_text(
            "✋️Solo se admiten imágenes🖼 como comprobante de pago💵",
            reply_markup=cancel_keyboard
        )

# —————— Balance de fichas ——————
    if texto == "Fichas🥏":
        fichas = await obtener_fichas(msg.from_user.id)
        return await msg.reply_text(
            f"🎲 Tu balance de fichas es: *{fichas}* 🥏",
            parse_mode="Markdown",
            reply_markup=get_casino_menu_keyboard()
        )

# — Botón Atrás⏮️ dinámico —
    if texto == "Atrás⏮️":
        ultimo = context.user_data.get("ultimo_menu")

        if ultimo == "casino":
            suscrito = await esta_suscrito(msg.from_user.id)
            context.user_data["ultimo_menu"] = "principal"
            return await msg.reply_text(
                "Bienvenido de vuelta al menú principal☑️",
                reply_markup=get_main_menu_keyboard(suscrito)
            )

        elif ultimo == "principal":
            return await msg.reply_text("Ya estás en el menú principal.")

        elif ultimo == "juegos":
            # volvemos al Casino
            context.user_data["ultimo_menu"] = "casino"
            return await msg.reply_text(
                "Volviendo al Casino🎲",
                reply_markup=get_casino_menu_keyboard()
            )

        # Si no coincide ninguno:
        return await msg.reply_text("No hay un menú anterior definido.")

# —————— Retiro de fichas ——————

    # Paso 1: el usuario pulsa “Retirar📤”
    if texto == "Retirar📤":
        context.user_data["awaiting_withdrawal_amount"] = True
        return await msg.reply_text(
            "¿Cuántas fichas deseas retirar?\n\n"
            "Escribe el número (mínimo 10) o presiona ❌️ Cancelar para volver.",
            reply_markup=ReplyKeyboardMarkup([["Cancelar❌️"]], resize_keyboard=True)
        )

    # Paso 2: leemos la cantidad que el usuario envía
    if context.user_data.get("awaiting_withdrawal_amount"):
        # Si cancela, volvemos al menú de Casino
        if texto == "Cancelar❌️":
            context.user_data.pop("awaiting_withdrawal_amount", None)
            return await msg.reply_text(
                "Operación cancelada.",
                reply_markup=get_casino_menu_keyboard()
            )
        # Validamos que sea un número positivo
        if not texto.isdigit() or int(texto) <= 0:
            return await msg.reply_text("❌ Ingresa un número válido.")
        monto = int(texto)
        # Verificamos mínimo de 10 fichas
        if monto < 10:
            return await msg.reply_text("❌ El mínimo de retiro es 10 fichas.")
        # Obtenemos el saldo actual
        fichas_actuales = await obtener_fichas(msg.from_user.id)
        # Verificamos que tenga suficientes fichas
        if monto > fichas_actuales:
            return await msg.reply_text("❌ No tienes suficientes fichas.")
        # Guardamos el monto y pasamos al siguiente paso
        context.user_data.pop("awaiting_withdrawal_amount")
        context.user_data["withdrawal_amount"] = monto
        context.user_data["awaiting_withdrawal_info"] = True
        # Calculamos el equivalente en cup (fichas * 9)
        equivalente = monto * 9
        return await msg.reply_text(
            f"Vas a retirar *{monto}* Fichas que equivalen a *{equivalente}cup💵*\n"
            "Ahora envía tu número de tarjeta💳 y número de teléfono📲 a confirmar☑️\n"
            "👉Todo en un solo mensaje \"solo números\"👈",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([["Cancelar❌️"]], resize_keyboard=True)
        )

    # Paso 3: el usuario envía sus datos de cuenta/teléfono
    if context.user_data.get("awaiting_withdrawal_info"):
        # Si cancela, limpiamos todo y volvemos al menú
        if texto == "Cancelar❌️":
            context.user_data.pop("awaiting_withdrawal_info", None)
            context.user_data.pop("withdrawal_amount", None)
            return await msg.reply_text(
                "Operación cancelada.",
                reply_markup=get_casino_menu_keyboard()
            )

        # Datos recibidos: preparamos solicitud
        datos = texto
        monto = context.user_data.pop("withdrawal_amount")
        context.user_data.pop("awaiting_withdrawal_info")

        # Recalculamos el equivalente en cup (fichas * 9)
        equivalente = monto * 9

        # Descontamos fichas en la base de datos
        await descontar_fichas(msg.from_user.id, monto)

        # Enviamos solicitud al admin con botón de procesar
        botones_admin = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "Procesar retiro✅",
                callback_data=f"procesar_retiro_{msg.from_user.id}_{monto}"
            )]
        ])
        caption = (
            f"🔁 *Solicitud de Retiro de Fichas*\n"
            f"Usuario: @{msg.from_user.username or msg.from_user.id}\n"
            f"ID: `{msg.from_user.id}`\n"
            f"Monto: *{equivalente}*cup💵\n"
            f"Datos de tarjeta/teléfono:\n`{datos}`"
        )
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=caption,
            parse_mode="Markdown",
            reply_markup=botones_admin
        )
        # Confirmación al usuario
        return await msg.reply_text(
            "✅ Tu solicitud de retiro ha sido enviada al administrador.\n"
            "En breve la procesará.",
            reply_markup=get_casino_menu_keyboard()
        )

        # —————— 3) Resto de tu lógica ——————
    return await handle_messages(update, context)

TMDB_BEARER_TOKEN = 'eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJhYzczMmZhODhjYzQzMzkzOTcyMjU4M2FjMDI2MzMyYiIsIm5iZiI6MTc0NDY1NDE2Ni44MzM5OTk5LCJzdWIiOiI2N2ZkNGY1NjMwMTUzNjMyODZkOTQ5NGUiLCJzY29wZXMiOlsiYXBpX3JlYWQiXSwidmVyc2lvbiI6MX0.Dn_SSRgOfKhJE25yt_j_JXXoQ3vFSzUUHGF2M9tioJs'
TMDB_API_KEY = 'ac732fa88cc433939722583ac026332b'

async def sumar_fichas_suscriptor(user_id: int, cantidad: int):
    """Suma fichas en la tabla de suscriptores (DB_SUSCRIPTORES)."""
    async with aiosqlite.connect(DB_SUSCRIPTORES) as conn:
        await conn.execute(
            "UPDATE suscriptores SET fichas = fichas + ? WHERE user_id = ?",
            (cantidad, user_id)
        )
        await conn.commit()

async def validar_en_api_externa(titulo: str) -> bool:
    headers = {
        'Authorization': f'Bearer {TMDB_BEARER_TOKEN}'
    }
    params = {
        'api_key': TMDB_API_KEY,
        'query': titulo,
        'language': 'es-ES',
        'page': 1
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        url_movie = 'https://api.themoviedb.org/3/search/movie'
        async with session.get(url_movie, params=params) as resp:
            data = await resp.json()
            if data.get('results'):
                return True
        url_tv = 'https://api.themoviedb.org/3/search/tv'
        async with session.get(url_tv, params=params) as resp:
            data = await resp.json()
            return bool(data.get('results'))

def guardar_sugerencia(uid, titulo):
    conn = sqlite3.connect(DB_SUGGESTIONS)
    c = conn.cursor()
    c.execute(
        "INSERT INTO suggestions(user_id, titulo, fecha) VALUES (?, ?, ?)",
        (uid, titulo, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    )
    conn.commit()
    conn.close()

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    uid = msg.from_user.id
    texto = msg.text.strip() if msg.text else ""
    chat_id = msg.chat.id
    is_admin = (chat_id == ADMIN_ID)
    print(f"🔔 handle_messages ► texto={repr(texto)}")
# Si está en modo RETIRO y toca "Atrás", vuelve al submenú de Referidos
    if texto in {"Atrás", "Atrás ⬅️"} and context.user_data.get('awaiting_retiro'):
        context.user_data.pop('awaiting_retiro', None)
        return await msg.reply_text(
            "Menú de Referidos☑️",
            reply_markup=get_referidos_menu_keyboard()
        )

    # Si no está en modo retiro, va al menú principal
    if texto in {"Atrás", "Atrás ⬅️"}:
        suscrito = await esta_suscrito(uid)
        return await msg.reply_text(
            "Menú Principal☑️",
            reply_markup=get_main_menu_keyboard(suscrito)
        )

# Si incluye “película(s)” o “serie(s)”, invalidar búsqueda
    if re.search(r'(?i)\bpel[ií]cula?s?\b|\bseries?\b', texto):
        await update.message.reply_text(
            "❗ Para buscar, escribe únicamente el nombre del título, sin la palabra “película” o “serie”.\n"
            "Ejemplo: Destino Final\n"
            "         Breaking Bad"
        )
        return

    # Si está en modo retiro, tratamos este texto como los datos de tarjeta y teléfono
    if context.user_data.get('awaiting_retiro'):
        context.user_data.pop('awaiting_retiro', None)
        monto = context.user_data.pop('retiro_monto', 0)
        datos = texto

        # Reiniciamos balance de una vez
        restar_balance(uid, monto)

        # Creamos el botón "Listo✅️"
        botones = InlineKeyboardMarkup([
            [InlineKeyboardButton("Listo✅️", callback_data=f"listo_{uid}")]
        ])

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🔁 *Solicitud de Retiro*\n"
                f"Usuario: @{msg.from_user.username or msg.from_user.id}\n"
                f"ID: `{uid}`\n"
                f"Monto: *{monto}* cup💵\n"
                f"Datos enviados:\n`{datos}`"
            ),
            parse_mode="Markdown",
            reply_markup=botones
        )

        return await msg.reply_text(
            "✅ Solicitud enviada al administrador.\nSerá procesada en breve.",
            reply_markup=get_referidos_menu_keyboard()
        )

    # ── 1) Manejo del botón Referidos ──────────────────────────────────
    # Capturamos cualquier texto que contenga “referidos” (minúsculas o mayúsculas)
    if "referidos" in texto.lower():
        print("🔔 detectado botón Referidos")
        context.user_data.pop('awaiting_sugerencia', None)
        context.user_data.pop('awaiting_retiro', None)

        n1 = await contar_referidos(uid)
        n2 = await contar_referidos_nivel2(uid)
        link = f"https://t.me/{BOT_USERNAME[1:]}?start=ref_{uid}"
        mensaje = (
            f"👋Gana 50cup💵 por cada usuario que se suscriba al bot por tu enlace y 25cup💵 por referidos de Nivel 2:\n\n"
            f"Referidos👤 Nivel 1: {n1}\nReferidos👤 Nivel 2: {n2}\n\n"
            f"Tu enlace🔗 de referidos es:\n{link}\n\n"
            "Al llegar a 5 Referidos de Nivel 1 tendrás tu próxima suscripción GRATIS✅️\n(Solo para suscriptores)"
        )
        return await msg.reply_text(
            mensaje,
            reply_markup=get_referidos_menu_keyboard(),
            disable_web_page_preview=True
        )

    # Botón de realizar sorteo del admin
    elif texto == "🎉REALIZAR SORTEO🎉" and msg.from_user.id == ADMIN_ID:
        boton = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎉REALIZAR SORTEO🎉", callback_data="realizar_sorteo")]
        ])
        return await msg.reply_text(
            "¿Estás listo para realizar el sorteo semanal?\nToca el botón de abajo para elegir al ganador al azar.",
            reply_markup=boton
        )

# estadísticas
    if texto == "Estadísticas📊":
        # Si es el admin, mostramos suscriptores activos como antes
        if update.effective_user.id == ADMIN_ID:
            async with aiosqlite.connect(DB_SUSCRIPTORES) as conn:
                cursor = await conn.execute(
                    "SELECT COUNT() FROM suscriptores WHERE fecha_expiracion >= ?",
                    (datetime.now().strftime("%Y-%m-%d"),)
                )
                row = await cursor.fetchone()
                total = row[0] if row else 0

        # Para el resto, contamos los /start únicos y sumamos 10500
        else:
            async with aiosqlite.connect(DB_STARTS) as conn:
                cursor = await conn.execute("SELECT COUNT(*) FROM starts")
                row = await cursor.fetchone()
                total = (row[0] if row else 0) + 10500

        return await update.message.reply_text(
            f"Total de usuarios👤: {total}",
            reply_markup=get_main_menu_keyboard(await esta_suscrito(update.effective_user.id))
        )

    if texto == "Balance💵":
        balance = await obtener_balance(uid)
        return await msg.reply_text(
            f"Tu balance es de: {balance} Cup💵",
            reply_markup=get_referidos_menu_keyboard()
        )

    if texto == "Retiro⬆️":
        suscrito = await esta_suscrito(uid)
        if not suscrito:
            return await msg.reply_text(
                "Para retirar tu balance primero debes activar tu suscripción",
                reply_markup=get_pago_keyboard()
            )

        bal = await obtener_balance(uid)
        if bal < 100:
            return await msg.reply_text(
                "Lo siento✋️, el mínimo de retiro es 100cup💵",
                reply_markup=get_referidos_menu_keyboard()
            )
        context.user_data['awaiting_retiro'] = True
        context.user_data['retiro_monto'] = bal
        return await msg.reply_text(
            f"Vas a hacer un retiro de {bal} cup💵\nEnvía tu número de tarjeta y número de teléfono a confirmar\n👉En un solo mensaje👈",
            reply_markup=get_retiro_keyboard()
        )

# —————— Comunidad ——————
    if texto == "👥COMUNIDAD🌍":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎥CUBAFLIX🎥 CANAL 1⚜️", url="https://t.me/peliculas_series_cubaflix")],
            [InlineKeyboardButton("🎥CUBAFLIX🎥 CANAL 2⚜️", url="https://t.me/estrenos_2025_cubaflix")],
            [InlineKeyboardButton("🎥CUBAFLIX🎥 GRUPO👥",     url="https://t.me/peliculas_2025_estreno")],
        ])
        await msg.reply_text(
            "👋Únete a nuestra comunidad de cinéfilos, abajo tienes el canal y el grupo, "
            "tanto en el canal como en el grupo se suben recomendaciones de películas que "
            "están disponibles en el bot, en el grupo puedes usar el comando /pedido y escribir "
            "el nombre de la película que desees y el bot encargado del grupo se encargará de "
            "enviarle el pedido al admin para agregarlo aquí.\n\n"
            "🌍ÚNETE A NUESTRA COMUNIDAD🌍",
            reply_markup=keyboard
        )
        return

# Explicación
    if texto == "💡 EXPLICACIÓN":
        explicacion_texto = (
            "ℹ️<b>EXPLICACIÓN SOBRE COMO FUNCIONAN LAS BÚSQUEDAS🔍:</b>\n\n"
            "Hay películas y series que tienen nombres con varias palabras ejemplo:\n\n"
            "➖️La casa de papel\n➖️The Last of us\n➖️Pídeme lo que quieras\n\n"
            "Entre otras muchas más. ¿Qué pasa con esto? Que como en la base de datos hay demasiado contenido, "
            "el bot encuentra muchas coincidencias con articulaciones como:\n\n"
            "<i>\"La, el, ellos, the, que, lo, una\"</i>\n\n"
            "O simplemente palabras que se parecen. Entonces la solución es escribir solo una o dos palabras del nombre, ejemplo:\n\n"
            "➖️Pídeme lo que quieras → pideme, quieras\n"
            "➖️Una Película de Minecraft → Minecraft, Una Película, Película\n"
            "➖️La casa de papel → papel, casa\n\n"
            "Y así con todo lo que busques y no encuentres...\n\n"
            "ℹ️<b>EXPLICACIÓN REFERIDOS NIVEL 2👥</b>\n"
            "Los referidos de nivel 2 son las personas que busquen los usuarios que invitaron ustedes. O sea, "
            "invitas a una persona y ese será un referido nivel 1. Todas las personas que busque ese usuario que entró por tu link serán tu referido nivel 2 "
            "y por lo tanto ganarás 25cup por cada uno.\n\n"
            "ℹ️<b>EXPLICACIÓN DEL GRUPO👥</b>\n"
            "En el grupo pueden escribir y debatir sobre lo que quieran y pueden sugerir películas usando el comando /pedido y el nombre de la película o serie. "
            "Si existe en TMDB (la página con la base de datos más grande del mundo de información sobre películas y series), "
            "el bot encargado del grupo le enviará la sugerencia a los admins encargados de buscar películas y series para agregarla a la base de datos del bot principal.\n\n"
            "ℹ️Cualquier duda la pueden escribir en el grupoℹ️"
        )
        await msg.reply_text(explicacion_texto, parse_mode="HTML")
        return

# —————— Envío masivo: activar modo de difusión (solo admin) ——————
    if texto == "📢Enviar a suscriptores" and msg.from_user.id == ADMIN_ID:
        context.user_data["awaiting_broadcast"] = True
        return await msg.reply_text(
            "Envía una foto con el caption que deseas enviar a todos los suscriptores.",
            reply_markup=ReplyKeyboardMarkup([["Cancelar❌️"]], resize_keyboard=True)
        )


# —————— Confirmación y envío del broadcast 
# ——————
    if context.user_data.get("awaiting_broadcast") == "confirm":
        # Cancelar
        if texto == "❌ Cancelar":
            await msg.reply_text(
                "🚫 Envío cancelado.",
                reply_markup=get_main_menu_keyboard(subscribed, is_admin)
            )
            context.user_data.pop("awaiting_broadcast", None)
            context.user_data.pop("broadcast_text", None)
            return

        # Enviar
        if texto == "✅ Enviar":
            broadcast_text = context.user_data.pop("broadcast_text", "")
            # 1) Obtenemos TODOS los que tocaron /start
            async with aiosqlite.connect(DB_STARTS) as conn:
                cursor = await conn.execute("SELECT user_id FROM starts")
                rows = await cursor.fetchall()
            user_ids = [r[0] for r in rows]

            # 2) Enviamos el mensaje a cada uno
            for uid in user_ids:
                try:
                    await context.bot.send_message(chat_id=uid, text=broadcast_text)
                except Exception:
                    pass  # opcional: loguear errores

            # 3) Confirmación al admin y reset de estado
            await msg.reply_text(
                "✅ Mensaje enviado a todos los usuarios que han usado /start.",
                reply_markup=get_main_menu_keyboard(subscribed, is_admin)
            )
            context.user_data.pop("awaiting_broadcast", None)
            return

    if texto == "➕ Sugerir Película":
    # Limpiamos otros estados por si acaso
        context.user_data.pop('awaiting_payment', None)
        context.user_data.pop('awaiting_retiro', None)

    # Activamos el modo sugerencia
        context.user_data['awaiting_sugerencia'] = True

    # Mostramos el mensaje solo UNA VEZ
        back_kb = ReplyKeyboardMarkup([["Atrás ⬅️"]], resize_keyboard=True)
        await msg.reply_text(
            "👋 Aquí puedes mandar✍️ el nombre de la Película🎥 o Serie🎞 que no encontraste.\n"
            "Se buscará🔍 en TMDB y si existe✅️, quedará registrada para subirla al bot en cuanto se pueda\n"
            "Asegúrate de escribir el nombre exacto👌 y vuelve a buscarla en el bot mañana✅️",
            reply_markup=back_kb
        )
        return

# Bloque para manejar el botón "🎉SORTEO SEMANAL🎉"
    if texto == "🎉SORTEO SEMANAL🎉":
        boton = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎉PARTICIPA EN EL SORTEO🎉", callback_data="participar_sorteo")]
        ])
        return await msg.reply_text(
            "🔹️Participa en los 🎉Sorteos🎉 semanales🗓 de 👑CUBAFLIX👑 y gana desde 500cup💵 hasta 5000cup💵🔹️\n"
            "⚜️Todas las semanas de Sábado a Jueves los usuarios van a tener la oportunidad de anotarse en los sorteos semanales "
            "de 👑CUBAFLIX👑 que se hacen todos los viernes en la noche🌙\n\n"
            "Requisito para participar:\n"
            "➖️Ser suscriptor del bot ya sea Clásico⚜️ o Premium💎\n\n"
            "🔹️Para participar solo toca el botón de abajo y Listo✅️ ya estarás dentro del sorteo del Viernes🔹️",
            reply_markup=boton
        )

# 3) Modo sugerencia
    if context.user_data.get('awaiting_sugerencia'):
        titulo = texto
        print(f"[DEBUG] Usuario pidió sugerencia: {titulo}")
        print(f"[DEBUG] Validando en TMDB...")
        existe = await validar_en_api_externa(titulo)
        print(f"[DEBUG] Resultado de validación: {existe}")
        if existe:
            guardar_sugerencia(uid, titulo)
            respuesta = f"✅ ¡Gracias! “{titulo}” quedó registrada para revisión."
        else:
            respuesta = f"❌ No he encontrado “{titulo}” en fuentes oficiales."

        context.user_data.pop('awaiting_sugerencia')

        suscrito = await esta_suscrito(uid)
        return await msg.reply_text(respuesta, reply_markup=get_main_menu_keyboard(suscrito))

    # 4) Evitar emojis
    if contiene_emoji(texto):
        return

# 5) Empieza la búsqueda
    loading = await msg.reply_text("Buscando🔍")

# Ejecutamos la búsqueda principal y aplicamos fallback desde dentro de buscar_peliculas()
    pelis = await buscar_peliculas(texto)
    resultados = pelis if pelis else await buscar_textos(texto)

    print(f"🔔 handle_messages: encontrados {len(resultados)} resultados para '{texto}'")

    # 8) Borra el “Buscando🔍”
    await context.bot.delete_message(
        chat_id=uid,
        message_id=loading.message_id
    )

    if not resultados:
        return await msg.reply_text(
            random.choice(MENSAJES_NO_ENCONTRADO),
            reply_markup=get_main_menu_keyboard(esta_suscrito(uid))
        )

# — Si es suscriptor (Clásica o Premium) y única coincidencia, envío directo —
    if len(resultados) == 1 and await esta_suscrito(uid):
        mid, txt = resultados[0]
        caption = f"{limpiar_caption(txt)} {BOT_USERNAME}"
        if await es_premium(uid):
            # Premium: copia normal sin restricciones
            return await context.bot.copy_message(
                chat_id=uid,
                from_chat_id=GRUPO_ID,
                message_id=mid,
                caption=caption
            )
        else:
            # Clásico: copia protegida
            return await context.bot.copy_message(
                chat_id=uid,
                from_chat_id=GRUPO_ID,
                message_id=mid,
                caption=caption,
                protect_content=True
            )

    # — Para todos los demás casos (no suscriptor o múltiples resultados), siempre paginar —
    context.user_data['search_results'] = resultados
    return await send_search_results_page(update, context, 0)
    # ── NUEVOS HANDLERS PARA GRUPO ─────────────────────────────────────────────

async def handle_group_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    video = msg.video
    if not video:
        return

    await guardar_mensaje_texto(
        mid=msg.message_id,
        usuario=msg.from_user.username or str(msg.from_user.id),
        texto=msg.caption or "[VIDEO]",
        enlaces=[video.file_id],
        fecha=msg.date.isoformat()
    )
    logging.info(f"[+] Vídeo registrado (file_id): {video.file_id}")

async def handle_group_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    text = msg.text or ""
    enlaces = []
    for ent in msg.entities or []:
        if ent.type in ('url', 'text_link'):
            url = ent.url if ent.type == 'text_link' else text[ent.offset:ent.offset+ent.length]
            enlaces.append(url)
    if enlaces:
        await guardar_mensaje_texto(
            mid=msg.message_id,
            usuario=msg.from_user.username or str(msg.from_user.id),
            texto=text,
            enlaces=enlaces,
            fecha=msg.date.isoformat()
        )
        logging.info(f"[+] Enlaces guardados: {enlaces}")

# ──────────────────────────────────────────────────────────────────────────


async def handle_group_video_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    doc = msg.document
    if not doc:
        return
    filename = doc.file_name or ""
    if not filename.lower().endswith((".mkv", ".avi", ".mp4", ".mov")):
        return

    await guardar_mensaje_texto(
        mid=msg.message_id,
        usuario=msg.from_user.username or str(msg.from_user.id),
        texto=msg.caption or filename,
        enlaces=[doc.file_id],
        fecha=msg.date.isoformat()
    )
    logging.info(f"[+] Video-documento guardado: {filename}")

async def borrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caption = " ".join(context.args)  # El texto después de /borrar
    deleted = 0

    # Verifica que se haya proporcionado un nombre para borrar
    if not caption:
        return await update.message.reply_text("Por favor, proporciona el nombre del video para borrarlo.")

    # Normaliza el texto de búsqueda para eliminar caracteres especiales y emojis
    caption_normalizado = normalize_text(caption)

    # Borra de peliculas.db usando coincidencia parcial (LIKE)
    async with aiosqlite.connect(DB_PELICULAS) as conn1:
        cursor1 = await conn1.execute(
            "SELECT caption FROM peliculas WHERE caption LIKE ?", ('%' + caption_normalizado + '%',)  # Usando LIKE para búsqueda parcial
        )
        videos_encontrados = await cursor1.fetchall()

    # Si no se encontró ningún video, informar al usuario
    if not videos_encontrados:
        return await update.message.reply_text("No se encontró ningún video que coincida con ese nombre.")

    # Mostrar los resultados encontrados
    mensaje_resultados = "Se encontraron los siguientes videos:\n"
    for idx, video in enumerate(videos_encontrados):
        mensaje_resultados += f"{idx + 1}. {video[0]}\n"

    # Pedir confirmación para borrar
    await update.message.reply_text(f"{mensaje_resultados}\n¿Deseas borrar alguno de estos videos? Responde con el número del video.")

    # Guardar los videos encontrados en el contexto para usar en el siguiente paso
    context.user_data['confirm_borrar'] = True
    context.user_data['videos_encontrados'] = videos_encontrados

    # Ahora esperamos la respuesta del usuario con un MessageHandler
    return await update.message.reply_text("Responde con el número del video que deseas borrar.")

# Este manejador captura la respuesta del usuario para borrar el video
async def procesar_respuesta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('confirm_borrar'):
        return

    try:
        # Captura el número de video que el usuario responde
        video_num = int(update.message.text.strip()) - 1  # Restamos 1 porque la lista comienza en 0
        videos_encontrados = context.user_data['videos_encontrados']

        if video_num < 0 or video_num >= len(videos_encontrados):
            return await update.message.reply_text("Número de video inválido. Intenta de nuevo.")

        # El video seleccionado para borrar
        video_a_borrar = videos_encontrados[video_num][0]

        # Proceder con el borrado del video
        deleted = 0
        # Borra de peliculas.db
        async with aiosqlite.connect(DB_PELICULAS) as conn1:
            cursor1 = await conn1.execute(
                "DELETE FROM peliculas WHERE caption = ?", (video_a_borrar,)
            )
            await conn1.commit()
            deleted += cursor1.rowcount

        # Borra de mensajes_textos.db
        async with aiosqlite.connect(DB_TEXTOS) as conn2:
            cursor2 = await conn2.execute(
                "DELETE FROM mensajes_textos WHERE texto = ?", (video_a_borrar,)
            )
            await conn2.commit()
            deleted += cursor2.rowcount

        # Confirmación final al usuario
        if deleted:
            await update.message.reply_text(f"Video '{video_a_borrar}' borrado con éxito✅️.")
        else:
            await update.message.reply_text("No se pudo borrar el video.")

    except ValueError:
        await update.message.reply_text("Por favor, proporciona un número válido.")

    # Limpiar los datos de confirmación
    context.user_data['confirm_borrar'] = False
    context.user_data['videos_encontrados'] = None

async def listar_suscriptores(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    async with aiosqlite.connect(DB_SUSCRIPTORES) as conn:
        cursor = await conn.execute(
            "SELECT COUNT() FROM suscriptores WHERE fecha_expiracion >= ?",
            (datetime.now().strftime("%Y-%m-%d"),)
        )
        row = await cursor.fetchone()

    total = row[0] if row else 0
    await update.message.reply_text(f"Usuarios activos: {total}")

async def anular_suscripcion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        return await update.message.reply_text("Uso: /anular <user_id o @username>")

    obj = context.args[0]
    uid = None
    tipo = None

    async with aiosqlite.connect(DB_SUSCRIPTORES) as conn:
        if obj.startswith("@"):
            cursor = await conn.execute(
                "SELECT user_id FROM suscriptores WHERE lower(username)=?",
                (obj.lower(),)
            )
            row = await cursor.fetchone()
            if not row:
                return await update.message.reply_text(f"No se encontró {obj}.")
            uid = row[0]
            tipo = "username"
        else:
            try:
                uid = int(obj)
                cursor = await conn.execute(
                    "SELECT 1 FROM suscriptores WHERE user_id=?",
                    (uid,)
                )
                if not await cursor.fetchone():
                    return await update.message.reply_text(f"No se encontró {obj}.")
                tipo = "user_id"
            except:
                return await update.message.reply_text("ID inválido.")

        # Anular suscripción
        await conn.execute(
            "UPDATE suscriptores SET estado='inactivo', fecha_expiracion=NULL WHERE user_id=?",
            (uid,)
        )
        await conn.commit()

    await update.message.reply_text(f"Suscripción anulada para {obj} ({tipo}).")


async def crear_bd_peliculas_async():
    async with aiosqlite.connect(DB_PELICULAS) as conn:
        # 1) Tabla normal con rowid automático
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS peliculas(
                rowid      INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER,
                caption    TEXT
            )
        ''')
        # 2) Índice FTS5 para búsquedas “al estilo Google”
        await conn.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS peliculas_fts
            USING fts5(caption, content='peliculas', content_rowid='rowid');
        ''')
        # 3) Reconstruye todo el índice al arrancar
        await conn.execute('''
            INSERT INTO peliculas_fts(peliculas_fts, rowid, caption)
            SELECT 'rebuild', rowid, caption FROM peliculas;
        ''')
        await conn.commit()

async def mostrar_estadisticas_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    # 1) Contamos siempre los /start en starts.db
    async with aiosqlite.connect(DB_STARTS) as conn:
        cursor = await conn.execute("SELECT COUNT(*) FROM starts")
        row = await cursor.fetchone()
        total_starts = row[0] if row else 0

    # 2) Si es admin mostramos total real; si no, sumamos 10 500
    total = total_starts if uid == ADMIN_ID else total_starts + 10500

    # 3) Enviamos resultado
    await update.message.reply_text(f"Suscriptores Activos👥: {total}\n\n🔥Miles de usuarios ya disfrutan de nuestro servicio🔥\nÚnete a nuestra comunidad presionando /start y elige tu plan mensual🗓")

async def crear_bd_suscriptores_async():
    async with aiosqlite.connect(DB_SUSCRIPTORES) as conn:
        # 1) Crea la tabla si no existe
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS suscriptores (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                fecha_expiracion TEXT,
                balance INTEGER DEFAULT 0,
                referrer INTEGER,
                estado TEXT,
                premium INTEGER DEFAULT 0
            )
        ''')
        await conn.commit()

        # 2) Comprueba si la columna 'fichas' ya está en la tabla
        cursor = await conn.execute("PRAGMA table_info(suscriptores)")
        columns = await cursor.fetchall()
        # Cada fila de 'columns' es (cid, name, type, notnull, dflt_value, pk)
        if not any(col[1] == "fichas" for col in columns):
            # 3) Si no existe, la añade
            await conn.execute("""
                ALTER TABLE suscriptores
                ADD COLUMN fichas INTEGER DEFAULT 0
            """)
            await conn.commit()

async def crear_bd_pagos_async():
    async with aiosqlite.connect(DB_PAGOS) as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS pagos_pendientes(
                user_id    INTEGER PRIMARY KEY,
                username   TEXT,
                timestamp  TEXT,
                photo_id   TEXT,
                sent       INTEGER DEFAULT 0,
                tipo_pago  TEXT
            )
        ''')
        await conn.commit()

async def crear_bd_starts_async():
    async with aiosqlite.connect(DB_STARTS) as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS starts(
                user_id INTEGER PRIMARY KEY,
                fecha TEXT
            )
        ''')
        await conn.commit()

async def job_enviar_sugerencias(app):
    """Envía las sugerencias recogidas hoy a las 22:00 y luego vacía la tabla."""
    today = datetime.now().strftime('%Y-%m-%d')

    async with aiosqlite.connect(DB_SUGGESTIONS) as conn:
        cursor = await conn.execute(
            "SELECT titulo FROM suggestions WHERE date(fecha) = ?", 
            (today,)
        )
        rows = await cursor.fetchall()

        if rows:
            titulos = [titulo for (titulo,) in rows]
            texto = "Sugerencias del día:\n" + "\n".join(titulos)
            await app.bot.send_message(chat_id=ADMIN_ID, text=texto)

        # Borrar todas las sugerencias (al final del día)
        await conn.execute("DELETE FROM suggestions")
        await conn.commit()

async def handle_response_to_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Verifica si el mensaje es una respuesta a otro mensaje
    if update.message.reply_to_message:
        # Verifica si el mensaje que está respondiendo tiene un video
        if update.message.reply_to_message.video:
            # Aquí procesas el video al que se le está respondiendo
            video_message_id = update.message.reply_to_message.message_id
            # Realiza las acciones que desees con el video
            await update.message.reply_text(f"Estás respondiendo al video con ID: {video_message_id}")

            # Si deseas, puedes continuar con más lógica aquí para lo que debe hacer la respuesta
        else:
            # Si no es un video, puedes manejar otro tipo de respuesta
            await update.message.reply_text("Este mensaje no es un video.")
    else:
        # Si el mensaje no es una respuesta a otro mensaje
        await update.message.reply_text("Este mensaje no está respondiendo a otro mensaje.")

async def eliminar_video_de_db(message_id):
    """Eliminar el video de la base de datos usando el message_id"""
    async with aiosqlite.connect(DB_PELICULAS) as conn:
        # Eliminar de la tabla de películas usando el message_id
        await conn.execute("DELETE FROM peliculas WHERE message_id = ?", (message_id,))
        await conn.commit()

    async with aiosqlite.connect(DB_TEXTOS) as conn:
        # Eliminar el texto asociado con el video en la tabla mensajes_textos
        await conn.execute("DELETE FROM mensajes_textos WHERE message_id = ?", (message_id,))
        await conn.commit()

async def resend_pending_payments(app):
    import html
    async with aiosqlite.connect(DB_PAGOS) as conn:
        cursor = await conn.execute(
            "SELECT user_id, photo_id, username, tipo_pago FROM pagos_pendientes WHERE sent = 0"
        )
        rows = await cursor.fetchall()

    for user_id, photo_id, username, tipo in rows:
        precio = 300 if tipo == "premium" else 200
        # Escapamos el username para HTML (protege underscores, etc.)
        safe_username = html.escape(username or str(user_id))
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("Aceptar✅️", callback_data=f"aceptar_{user_id}")],
            [InlineKeyboardButton("Rechazar❌️", callback_data=f"rechazar_{user_id}")]
        ])
        caption = (
            "<b>📸 Comprobante (REINTENTO)</b>\n"
            f"Usuario: @{safe_username}\n"
            f"ID: <code>{user_id}</code>\n"
            f"Monto: <b>{precio}cup💵</b>"
        )
        try:
            await app.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=photo_id,
                caption=caption,
                reply_markup=buttons,
                parse_mode="HTML"
            )
        except Exception as e:
            logging.warning(f"No pude reenviar comprobante de {user_id}: {e}")
            continue

        # Marcamos como enviado
        async with aiosqlite.connect(DB_PAGOS) as conn2:
            await conn2.execute(
                "UPDATE pagos_pendientes SET sent = 1 WHERE user_id = ?",
                (user_id,)
            )
            await conn2.commit()

async def error_handler(update, context):
    # Ignoramos bloqueos y timeouts de envíos en background
    if isinstance(context.error, (Forbidden, TimedOut)):
        return
    # Otros errores sí los loggeamos
    logging.exception(f"Error procesando update {update}: {context.error}")


def main():
    # Crea la aplicación del bot
    app = ApplicationBuilder().token(TOKEN).build()

    # Handler para botón +18
    app.add_handler(
        MessageHandler(
            F.Text("CubafliXXX🔥"),
            handle_xxx18_button
        )
    )

    # Manejador de errores
    app.add_error_handler(error_handler)

    # Configura el scheduler con el loop actual
    loop = asyncio.get_event_loop()
    scheduler = AsyncIOScheduler(event_loop=loop)
    scheduler.add_job(resend_pending_payments, 'interval', minutes=5, args=[app])
    scheduler.start()

    # Inicializa las bases de datos antes de arrancar
    asyncio.get_event_loop().run_until_complete(init_databases())

    # Comandos principales
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("borrar", borrar))
    app.add_handler(CommandHandler("anular", anular_suscripcion))
    app.add_handler(CommandHandler("suscriptores", listar_suscriptores))
    app.add_handler(CommandHandler("cancelar", cancel_payment))
    app.add_handler(CommandHandler("sugerir", sugerir_pelicula))
    app.add_handler(CommandHandler("dinero", dinero))
    app.add_handler(CommandHandler("estadisticas", mostrar_estadisticas_usuario))
    app.add_handler(CommandHandler("limpiar", limpiar_contadores))
    app.add_handler(CommandHandler("aceptarclasico", aceptar_clasico))
    app.add_handler(CommandHandler("aceptarpremium", aceptar_premium))
    app.add_handler(CommandHandler("cancelar_pago", cancelar_pagoxxx18))
    # ——— Botones especiales +18 ———
    app.add_handler(CallbackQueryHandler(
        handle_buttons,
        pattern=r'^(access_xxx18|aceptar_xxx18_\d+|rechazar_xxx18_\d+)$'
    ))

    # ——— Botones de suscripción (se manejan en handle_buttons) ———
    # (Bloque eliminado para que "clasica" y "premium" fluyan a handle_buttons)

    # ——— Resto de botones normales ———
# ——— Resto de botones normales (incluye suscripciones) ———
# ——— Resto de botones normales ———
# ——— Resto de botones normales, incluyendo sorteos, paginación y selección ———
    app.add_handler(CallbackQueryHandler(
        handle_buttons,
        pattern=(
            r'^(clasica|premium|suscripcion_clasica_anual|suscripcion_premium_anual|'
            r'info_suscripciones|pagar|.*_menu|pagina_anterior|pagina_siguiente|'
            r'ver_sorteo|ver_referidos|menu|page_\d+|seleccionar\d+|participar_sorteo)$'
        )
    ))
    # ——— Botones de pagos ———
    app.add_handler(CallbackQueryHandler(
        handle_payment_action,
        pattern=r'^(aceptar|rechazar|deposito_aceptar|deposito_rechazar)_(?!xxx18_)\d+$'
    ))

    # Handlers generales de mensajes
# Detecta “serie” o “series”  
    app.add_handler(
        MessageHandler(
            F.TEXT & F.Regex(re.compile(r'^(serie|series)$', re.IGNORECASE)),
            responder_series
        )
    )

# Handler para el texto que envía el botón “Estadísticas📊”
    app.add_handler(
        MessageHandler(
            F.TEXT & F.Regex(r"^Estadísticas📊$"),
            mostrar_estadisticas_usuario
        )
    )

    # Detecta “película” o “peliculas”  
    app.add_handler(
        MessageHandler(
            F.TEXT & F.Regex(re.compile(r'^(pel[ií]cula|peliculas)$', re.IGNORECASE)),
            responder_peliculas
        )
    )

    # Handler genérico de búsqueda  
    app.add_handler(
        MessageHandler(
            F.TEXT & ~F.COMMAND,
            handle_messages    # ← era handle_texto_para_buscar, cámbialo al nombre real de tu función de router
        )
    )
    app.add_handler(MessageHandler(F.PHOTO & F.ChatType.PRIVATE, handle_photo))
    app.add_handler(MessageHandler(
        F.TEXT & ~F.COMMAND & F.ChatType.PRIVATE,
        text_router
    ))
    app.add_handler(MessageHandler(
        F.Chat(chat_id=GRUPO_ID) & F.VIDEO,
        handle_group_video
    ))
    app.add_handler(MessageHandler(
        F.Chat(chat_id=GRUPO_ID) & F.Document.VIDEO,
        handle_group_video_document
    ))
    app.add_handler(MessageHandler(
        F.Chat(chat_id=GRUPO_ID) & (F.Entity("url") | F.Entity("text_link")),
        handle_group_links
    ))
    app.add_handler(MessageHandler(F.Text(), procesar_respuesta))
    app.add_handler(MessageHandler(F.Text(), handle_response_to_video))

    # Jobs periódicos
    async def _job_suspender(context: ContextTypes.DEFAULT_TYPE):
        await suspend_expired_subscriptions(context.application)

    async def _job_sugerencias(context: ContextTypes.DEFAULT_TYPE):
        await job_enviar_sugerencias(context.application)

    app.job_queue.run_repeating(
        _job_suspender,
        interval=1800,
        first=0
    )

    tz_toronto = timezone(timedelta(hours=-4))
    app.job_queue.run_daily(
        _job_sugerencias,
        time=dtime(hour=22, minute=0, tzinfo=tz_toronto)
    )

    # Mensaje de arranque y polling
    logging.info("Bot en funcionamiento…")
    app.run_polling()


if __name__ == "__main__":
    main()


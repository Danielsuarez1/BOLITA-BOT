import pytz
import sqlite3
import telebot
import time
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
# TOKEN de tu bot de Telegram
API_TOKEN = '7767842183:AAFQwOHvk6W76W2x4ZCg3h2hyIrsvtD-tL4'
bot = telebot.TeleBot(API_TOKEN)

# Base de datos SQLite
db_path = 'bolita.db'
MAX_CUPO = 1000  # Cupo inicial por número

# IDs de administradores autorizados
admin_ids = [1140690034]

# Tarjetas de destino para el pago
tarjetas = ['9227-0699-9529-7895', '6543210987654321']

# Variable para guardar el último número ganador
ultimo_numero_ganador = None
numeros_bloqueados = set()
# Conexión y creación de tablas
conn = sqlite3.connect(db_path, check_same_thread=False)
cursor = conn.cursor()

# Crear tabla de números (si no existe)
cursor.execute('''
CREATE TABLE IF NOT EXISTS numbers (
    num INTEGER PRIMARY KEY,
    remaining INTEGER NOT NULL
)
''')

# Crear tabla de apuestas (si no existe)
cursor.execute('''
CREATE TABLE IF NOT EXISTS bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT,
    num INTEGER NOT NULL,
    amount INTEGER NOT NULL,
    placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS subscribers (
        user_id INTEGER PRIMARY KEY
    )
''')
conn.commit()

# Asegurar columna username
try:
    cursor.execute('ALTER TABLE bets ADD COLUMN username TEXT')
except sqlite3.OperationalError:
    pass
conn.commit()

# Inicializar los números 1-100 si la tabla está vacía
cursor.execute('SELECT COUNT(*) FROM numbers')
if cursor.fetchone()[0] == 0:
    cursor.executemany(
        'INSERT INTO numbers (num, remaining) VALUES (?, ?)',
        [(i, MAX_CUPO) for i in range(1, 101)]
    )
    conn.commit()
# Asegurar columna bet_type
try:
    cursor.execute('ALTER TABLE bets ADD COLUMN bet_type TEXT')
except sqlite3.OperationalError:
    pass
conn.commit()
# Estados de usuarios: 'awaiting_number'|'awaiting_amount'|'awaiting_payment'
user_states = {}

# --- MANEJADORES DEL BOT ---


@bot.message_handler(commands=['start'])
def start_handler(message):
    user_id = message.from_user.id
    username = message.from_user.first_name or message.from_user.username or "jugador"

    # ¿Es usuario nuevo?
    cursor.execute('SELECT 1 FROM subscribers WHERE user_id = ?', (user_id,))
    es_nuevo = cursor.fetchone() is None

    if es_nuevo:
        # Registrar nuevo suscriptor
        cursor.execute('INSERT INTO subscribers (user_id) VALUES (?)', (user_id,))
        conn.commit()

        # Mensaje de bienvenida + menú de jugadas
        welcome_text = (
            f"👋 BIENVENIDO, {username}!\n"
            "🔷️ SOY EL ÚNICO BOT DE CUBA🇨🇺\n\n"
            "🔄100% AUTOMATIZADO🔄\n\n"
            "Para hacer jugadas en LA BOLITA⚜️\n"
            "🔷️ A continuación te enseño las opciones que tengo:\n\n"
            "🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴\n"
            "LAS JUGADAS DISPONIBLES SON LAS SIGUIENTES:\n"
            "--------------------\n"
            "FIJO: 80cup💵\n"
            "--------------------\n"
            "CORRIDO: 30cup💵\n"
            "--------------------\n"
            "PARLÉ: 1000cup💵\n\n"
            "⚜️⚜️⚜️⚜️⚜️⚜️⚜️⚜️⚜️⚜️⚜️⚜️⚜️⚜️\n"
            "SELECCIONA EL BOTÓN CORRESPONDIENTE A LA JUGADA QUE QUIERES HACER\n"
            "👇👇👇👇"
        )

        inline = InlineKeyboardMarkup()
        inline.add(InlineKeyboardButton("JUGAR AL FIJO💵", callback_data="jugar_fijo"))
        inline.add(InlineKeyboardButton("JUGAR AL CORRIDO💵", callback_data="jugar_corrido"))
        inline.add(InlineKeyboardButton("JUGAR AL PARLÉ💵", callback_data="jugar_parle"))

        bot.send_message(message.chat.id, welcome_text, reply_markup=inline)
    else:
        # Ya registrado → usar el menú de jugadas sin bienvenida
        menu_text = (
            "🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴\n"
            "LAS JUGADAS DISPONIBLES SON LAS SIGUIENTES:\n"
            "--------------------\n"
            "FIJO: 80cup💵\n"
            "--------------------\n"
            "CORRIDO: 30cup💵\n"
            "--------------------\n"
            "PARLÉ: 1000cup💵\n\n"
            "⚜️⚜️⚜️⚜️⚜️⚜️⚜️⚜️⚜️⚜️⚜️⚜️⚜️⚜️\n"
            "SELECCIONA EL BOTÓN CORRESPONDIENTE A LA JUGADA QUE QUIERES HACER\n"
            "👇👇👇👇"
        )

        inline = InlineKeyboardMarkup()
        inline.add(InlineKeyboardButton("JUGAR AL FIJO💵", callback_data="jugar_fijo"))
        inline.add(InlineKeyboardButton("JUGAR AL CORRIDO💵", callback_data="jugar_corrido"))
        inline.add(InlineKeyboardButton("JUGAR AL PARLÉ💵", callback_data="jugar_parle"))

        bot.send_message(message.chat.id, menu_text, reply_markup=inline)

    # Siempre mostrar teclado de Estadísticas después
    reply_kb = ReplyKeyboardMarkup(resize_keyboard=True)
    reply_kb.add(KeyboardButton("📊Estadísticas"))
    bot.send_message(message.chat.id, "Menú Principal🔹️", reply_markup=reply_kb)

@bot.message_handler(func=lambda m: m.text == '📊Estadísticas')
def reply_estadisticas(message):
    # Obtener número real de suscriptores
    cursor.execute('SELECT COUNT(*) FROM subscribers')
    real = cursor.fetchone()[0]

    # Si es admin, mostrar real; si no, sumar 1500
    if message.from_user.id in admin_ids:
        count = real
    else:
        count = real + 1500

    bot.send_message(message.chat.id, f"Jugadores Activos: {count}")

@bot.message_handler(commands=['suscriptores'])
def suscriptores_handler(message):
    if message.from_user.id not in admin_ids:
        return
    cursor.execute('SELECT COUNT(*) FROM subscribers')
    count = cursor.fetchone()[0]
    bot.reply_to(message, f"Usuarios👥️: {count}")

@bot.callback_query_handler(func=lambda call: call.data == 'jugar_fijo')
def jugar_fijo_handler(call):
    # 1) Marcar estado para iniciar apuesta de tipo FIJO
    user_states[call.from_user.id] = {'state': 'awaiting_number', 'bet_type': 'fijo'}

    # 2) Confirmar el callback para que no quede “cargando”
    bot.answer_callback_query(call.id)

    # 3) Enviar el prompt de número, indicando el pago fijo
    bot.send_message(
        call.message.chat.id,
        "✍️ Envía un número del 1 al 100 para jugar **FIJO**\n" +
        "Se paga a **80 cup** por número.",
        parse_mode='Markdown'
    )

@bot.callback_query_handler(func=lambda call: call.data == 'jugar_corrido')
def jugar_corrido_handler(call):
    user_states[call.from_user.id] = {'state': 'awaiting_number', 'bet_type': 'corrido'}
    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        "✍️ Envía un número del 1 al 100 para jugar **CORRIDO**\n" +
        "Se paga a **30 cup** por número.",
        parse_mode='Markdown'
    )

@bot.callback_query_handler(lambda c: c.data == 'start_bet')
def start_bet_handler(call):
    user_states[call.from_user.id] = {'state': 'awaiting_number'}
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, 'Envía un número del 1 al 100 para jugar.')

@bot.message_handler(func=lambda m: m.text and m.text.isdigit() and (
    m.from_user.id in admin_ids or
    user_states.get(m.from_user.id, {}).get('state') == 'awaiting_number'
))
def number_or_admin_handler(message):
    user_id = message.from_user.id
    num = int(message.text)

    # --- ADMIN: registrar número ganador y pagar premios ---
    if user_id in admin_ids:
        global ultimo_numero_ganador
        ultimo_numero_ganador = num

        # Buscar ganadores agrupados por usuario
        cursor.execute('SELECT user_id, username, num, amount FROM bets')
        todas = cursor.fetchall()

        # Obtener números ganadores desde el número de 7 dígitos
        numero_str = str(ultimo_numero_ganador).zfill(7)
        fijo   = int(numero_str[1:3])
        corr1  = int(numero_str[3:5])
        corr2  = int(numero_str[5:7])

        ganadores = []

        for uid, username, jugado, monto in todas:
            tipo_jugada = get_user_bet_type(uid)  # deberás implementar esta si guardas tipo

            if jugado == fijo:
                if tipo_jugada == 'fijo':
                    premio = monto * 80
                else:  # corrido acierta el fijo
                    premio = monto * 30
                ganadores.append((uid, premio))
            elif jugado == corr1 or jugado == corr2:
                premio = monto * 30
                ganadores.append((uid, premio))

        for uid, premio in ganadores:
            bot.send_message(uid, f"🎉Felicidades🥳, ganaste🍀: {premio} Cup💵")
            bot.send_message(uid, "Mándame tu número de tarjeta💳 y número de teléfono📱 a confirmar\n👉EN  UN  SOLO  MENSAJE 👈")
            user_states[uid] = {'state': 'awaiting_card', 'premio': premio, 'num': num}

        # Reiniciar la base de datos
        cursor.execute('UPDATE numbers SET remaining = ?', (MAX_CUPO,))
        cursor.execute('DELETE FROM bets')
        conn.commit()

        # Limpiar estados innecesarios
        for uid in list(user_states.keys()):
            if uid not in [g[0] for g in ganadores]:
                user_states.pop(uid)

        numeros_bloqueados.clear()
        bot.reply_to(message, f"Número ganador registrado: {num}\nBases de datos reiniciadas.")
        return

    # --- USUARIO NORMAL: elegir número ---
    if not (1 <= num <= 100):
        bot.reply_to(message, "Por favor envía un número entre 1 y 100.")
        return

    if num in numeros_bloqueados:
        bot.reply_to(
            message,
            "Ese número está pendiente a un pago, debe esperar unos minutos o escribir otro número."
        )
        user_states[user_id] = {'state': 'awaiting_number'}
        return

    # Consultar cupo
    cursor.execute('SELECT remaining FROM numbers WHERE num = ?', (num,))
    remaining = cursor.fetchone()[0]
    if remaining < 25:
        bot.reply_to(message, f"El cupo del número {num} está lleno. Por favor elige otro.")
        return

    # Retener el tipo de jugada si ya estaba (fijo o corrido)
    bet_type = user_states.get(user_id, {}).get('bet_type', 'fijo')

    user_states[user_id] = {
        'state': 'awaiting_amount',
        'num': num,
        'bet_type': bet_type
    }

    bot.reply_to(
        message,
        f"Seleccionaste el número {num} para jugar al {bet_type.upper()}.\n"
        f"Apuesta mínima: 25 cup. Cupo máximo disponible: {remaining} cup.\n"
        "¿Cuánto quieres apostar?"
    )

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get('state') == 'awaiting_card')
def recibir_tarjeta(message):
    user_id = message.from_user.id
    state = user_states[user_id]
    premio = state['premio']

    bot.reply_to(message, "✋️Espere que se realice su pago✋️")

    # Enviar al admin
    info = message.text
    caption = (
        f"🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔\n"
        f"Monto a pagar por el número ganador: {premio} cup💵\n\n"
        f"{info}"
    )
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Listo✅️", callback_data=f"pago_listo_{user_id}"))

    for admin in admin_ids:
        bot.send_message(admin, caption, reply_markup=markup)

    user_states[user_id] = {'state': 'awaiting_payment_confirmation'}

@bot.callback_query_handler(func=lambda call: call.data.startswith('pago_listo_'))
def confirmar_pago(call):
    uid = int(call.data.split('_')[-1])
    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    except:
        pass

    # Enviar mensaje de confirmación al usuario
    bot.send_message(uid, "💵Pago Realizado✅️")

    # Mostrar botón para hacer nueva jugada
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton('HACER JUGADA✍️', callback_data='start_bet'))
    bot.send_message(
        uid,
        "Para jugarle a un número presiona el botón de abajo👇",
        reply_markup=markup
    )

    # Eliminar al usuario de los estados
    user_states.pop(uid, None)
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda m: m.text is not None)
def text_handler(message):
    user_id = message.from_user.id
    state = user_states.get(user_id)

    if state and state.get('state') == 'awaiting_amount':
        try:
            amount = int(message.text)
        except ValueError:
            bot.reply_to(message, "Monto inválido. Debes enviar un número.")
            return

        num = state['num']
        cursor.execute('SELECT remaining FROM numbers WHERE num = ?', (num,))
        remaining = cursor.fetchone()[0]

        if amount < 25 or amount > remaining:
            bot.reply_to(
                message,
                f"Cantidad no permitida. Debes apostar entre 25 y {remaining} cup."
            )
            return

        user_states[user_id] = {'state': 'awaiting_payment', 'num': num, 'amount': amount}
        bot.reply_to(
            message,
            f"Perfecto. Debes enviar {amount} pesos a la tarjeta {tarjetas[0]}\n"
            f"Número a confirmar: 59420036.\n"
            f"Por favor envía la captura de pantalla como imagen."
        )

    elif state and state.get('state') == 'awaiting_payment':
        bot.reply_to(message, "Solo se admiten imágenes como comprobante de pago.")

@bot.message_handler(
    func=lambda m: m.content_type == 'photo'
               and user_states.get(m.from_user.id, {}).get('state') == 'awaiting_payment',
    content_types=['photo']
)
def photo_handler(message):
    user_id = message.from_user.id
    state = user_states[user_id]
    num = state['num']
    amount = state['amount']
    uname = message.from_user.username or ''
    if uname:
        uname = '@' + uname

    # Enviar foto y datos al admin
    caption = (
        f"Usuario: {uname}\n"
        f"Id: {user_id}\n"
        f"Cantidad que apostó: {amount} cup"
    )
    admin_markup = InlineKeyboardMarkup()
    admin_markup.add(
        InlineKeyboardButton("Aceptar✅️", callback_data=f"accept_{user_id}_{num}_{amount}"),
        InlineKeyboardButton("Rechazar❌️", callback_data=f"reject_{user_id}_{num}_{amount}")
    )
    for admin in admin_ids:
        bot.send_photo(admin, message.photo[-1].file_id, caption=caption, reply_markup=admin_markup)

    bot.reply_to(message, "EN BREVE SE REVISARÁ LA JUGADA✋️\nY SE LE NOTIFICARÁ SI FUE\n ACEPTADA✅️ O NO❌️")

    # Nuevo menú de jugadas tras comprobante
    menu_text = (
        "🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴\n"
        "LAS JUGADAS DISPONIBLES SON LAS SIGUIENTES:\n"
        "--------------------\n"
        "FIJO: 80cup💵\n"
        "--------------------\n"
        "CORRIDO: 30cup💵\n"
        "--------------------\n"
        "PARLÉ: 1000cup💵\n\n"
        "⚜️⚜️⚜️⚜️⚜️⚜️⚜️⚜️⚜️⚜️⚜️⚜️⚜️\n"
        "SELECCIONA EL BOTÓN CORRESPONDIENTE A LA JUGADA QUE QUIERES HACER\n"
        "👇👇👇👇"
    )
    user_markup = InlineKeyboardMarkup()
    user_markup.add(InlineKeyboardButton("JUGAR AL FIJO💵", callback_data="jugar_fijo"))
    user_markup.add(InlineKeyboardButton("JUGAR AL CORRIDO💵", callback_data="jugar_corrido"))
    user_markup.add(InlineKeyboardButton("JUGAR AL PARLÉ💵", callback_data="jugar_parle"))
    bot.send_message(message.chat.id, menu_text, reply_markup=user_markup)

    # Bloquear número y actualizar estado
    numeros_bloqueados.add(num)
    user_states[user_id] = {'state': 'awaiting_admin', 'num': num, 'amount': amount}

@bot.message_handler(
    func=lambda m: m.content_type == 'photo'
               and m.from_user.id in admin_ids
               and m.caption,
    content_types=['photo']
)
def admin_foto_con_numero_handler(message):
    global ultimo_numero_ganador

    numero_str = message.caption.strip()
    if not numero_str.isdigit() or len(numero_str) != 7:
        bot.reply_to(message, "Error: Debes enviar exactamente 7 dígitos.")
        return

    # Extraer posiciones
    centena = numero_str[0]
    fijo    = int(numero_str[1:3])
    corr1   = int(numero_str[3:5])
    corr2   = int(numero_str[5:7])

    # Guardar el número original como "último número ganador"
    ultimo_numero_ganador = int(numero_str)

    # Buscar apuestas aceptadas
    cursor.execute('SELECT user_id, num, amount, bet_type FROM bets')
    apuestas = cursor.fetchall()
    ganadores = []

    for user_id, jugado, monto, tipo in apuestas:
        if tipo == 'fijo':
            # Solo gana si coincide con el número fijo
            if jugado == fijo:
                premio = monto * 80
                ganadores.append((user_id, premio))
        elif tipo == 'corrido':
            # Solo gana si coincide con alguno de los dos corridos
            if jugado == corr1 or jugado == corr2:
                premio = monto * 30
                ganadores.append((user_id, premio))

    # Notificar ganadores y pasar a estado de pago
    for uid, premio in ganadores:
        bot.send_message(uid, f"🎉Felicidades🥳, ganaste🍀: {premio} Cup💵")
        bot.send_message(uid, "Mándame tu número de tarjeta💳 y número de teléfono📱 a confirmar\n👉EN  UN  SOLO  MENSAJE 👈")
        user_states[uid] = {'state': 'awaiting_card', 'premio': premio, 'num': fijo}

    # Reiniciar base de datos y cupos
    cursor.execute('UPDATE numbers SET remaining = ?', (MAX_CUPO,))
    cursor.execute('DELETE FROM bets')
    conn.commit()

    # Limpiar estados de no-ganadores
    for uid in list(user_states.keys()):
        if uid not in [g[0] for g in ganadores]:
            user_states.pop(uid)
    numeros_bloqueados.clear()

    # Preparar y enviar resultado al canal
    tz = pytz.timezone('America/Havana')
    hour = datetime.now(tz).hour
    turno = "Día🌞" if 6 <= hour < 18 else "Noche🌙"

    header  = "🌴LOTERÍA DE LA FLORIDA🌴"
    divider = "♦️" * 13
    caption_text = (
        f"{header}\n"
        f"Resultado de la {turno}:\n"
        f"**{centena}-{fijo}-{corr1}-{corr2}**\n"
        f"🔹️Centena: **{centena}**\n"
        f"🔸️Fijo: **{fijo}**\n"
        f"▫️Corridos: **{corr1}-{corr2}**\n"
        f"{divider}\n"
        "Se paga el número a 80cup💵"
    )

    try:
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        downloaded = bot.download_file(file_info.file_path)
        from io import BytesIO
        stream = BytesIO(downloaded)
        stream.name = "resultado.jpg"

        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("🌴LA BOLITA CUBANA BOT🇨🇺", url="https://t.me/la_bolita_cuba_bot"),
            InlineKeyboardButton("📊Estadísticas", callback_data="estadisticas")
        )

        bot.send_photo(
            -1001585975309,  # ID del canal
            photo=stream,
            caption=caption_text,
            parse_mode='Markdown',
            reply_markup=markup
        )

        bot.reply_to(message, "Números ganadores enviados al canal y premios procesados.")
    except Exception as e:
        bot.reply_to(message, f"Error al enviar al canal: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith(('accept_', 'reject_')))
def callback_handler(call):
    action, uid, num, amt = call.data.split('_')
    user_id = int(uid)
    num = int(num)
    amount = int(amt)

    # Quitar botones del mensaje del admin
    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    except:
        pass

    if action == 'accept':
        # Obtener tipo de jugada del estado actual
        bet_type = user_states.get(user_id, {}).get('bet_type', 'fijo')

        # Guardar apuesta con tipo en la base de datos
        cursor.execute(
            'INSERT INTO bets (user_id, username, num, amount, bet_type) VALUES (?, ?, ?, ?, ?)',
            (user_id, '', num, amount, bet_type)
        )
        cursor.execute(
            'UPDATE numbers SET remaining = remaining - ? WHERE num = ?',
            (amount, num)
        )
        conn.commit()

        bot.send_message(user_id, "Su jugada fue aceptada✅️")
    else:
        bot.send_message(user_id, "Su jugada fue Rechazada❌️")

    # Mostrar menú de jugadas después
    menu_text = (
        "👋¡Listo! Cuando quieras volver a jugar:\n\n"
        "🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴\n"
        "LAS JUGADAS DISPONIBLES SON LAS SIGUIENTES:\n"
        "--------------------\n"
        "FIJO: 80cup💵\n"
        "--------------------\n"
        "CORRIDO: 30cup💵\n"
        "--------------------\n"
        "PARLÉ: 1000cup💵\n\n"
        "⚜️⚜️⚜️⚜️⚜️⚜️⚜️⚜️⚜️⚜️⚜️⚜️⚜️⚜️\n"
        "SELECCIONA EL BOTÓN CORRESPONDIENTE A LA JUGADA QUE QUIERES HACER\n"
        "👇👇👇👇"
    )
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("JUGAR AL FIJO💵", callback_data="jugar_fijo"))
    markup.add(InlineKeyboardButton("JUGAR AL CORRIDO💵", callback_data="jugar_corrido"))
    markup.add(InlineKeyboardButton("JUGAR AL PARLÉ💵", callback_data="jugar_parle"))
    bot.send_message(user_id, menu_text, reply_markup=markup)

    # Limpiar estado y desbloquear número
    user_states.pop(user_id, None)
    numeros_bloqueados.discard(num)
    bot.answer_callback_query(call.id)

print("Bot iniciado (modo resiliente)...")
while True:
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=20)
    except Exception as e:
        print("⚠️ Polling falló:", e)
        print("↪️ Reintentando en 5 segundos…")
        time.sleep(5)

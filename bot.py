import logging
import sys
import uuid
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web, ClientSession
from urllib.parse import urlencode
import traceback
import os

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)
logger.info("Начало выполнения скрипта")

# Настройки
TOKEN = "7669060547:AAF1zdVIBcmmFKQGhQ7UGUT8foFKW4EBVxs"
YOOMONEY_WALLET = "4100118178122985"
KOYEB_URL = "https://favourite-brinna-createthisshit-eca5920c.koyeb.app/save_payment"
WEBHOOK_HOST = "https://d-wd9e.onrender.com"
WEBHOOK_PATH = "/telegram"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# Инициализация бота
logger.info("Попытка инициализации бота")
try:
    bot = Bot(token=TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(bot, storage=storage)
    logger.info("Бот и диспетчер успешно инициализированы")
except Exception as e:
    logger.error(f"Ошибка инициализации бота: {e}")
    sys.exit(1)

# Инициализация SQLite
def init_db():
    conn = sqlite3.connect("payments.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS payments
                 (label TEXT PRIMARY KEY, user_id TEXT, status TEXT)''')
    conn.commit()
    conn.close()

init_db()

# Обработчик команды /start
@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    try:
        user_id = str(message.from_user.id)
        logger.info(f"Получена команда /start от user_id={user_id}")
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton(text="Пополнить", callback_data="pay"))
        welcome_text = (
            "Тариф: фулл\n"
            "Стоимость: 2.00 🇷🇺RUB\n"
            "Срок действия: 1 месяц\n\n"
            "Вы получите доступ к следующим ресурсам:\n"
            "• Мой кайф (канал)"
        )
        await message.answer(welcome_text, reply_markup=keyboard)
        logger.info(f"Отправлен ответ на /start для user_id={user_id}")
    except Exception as e:
        logger.error(f"Ошибка в обработчике /start: {e}")
        await message.answer("Произошла ошибка, попробуйте позже.")

# Обработчик команды /pay и кнопки "Пополнить"
@dp.message_handler(commands=['pay'])
@dp.callback_query_handler(text="pay")
async def pay_command(message_or_callback: types.Message | types.CallbackQuery):
    try:
        if isinstance(message_or_callback, types.Message):
            user_id = str(message_or_callback.from_user.id)
            chat_id = message_or_callback.chat.id
        else:
            user_id = str(message_or_callback.from_user.id)
            chat_id = message_or_callback.message.chat.id

        logger.info(f"Получена команда /pay от user_id={user_id}")

        # Создание платёжной ссылки
        payment_label = str(uuid.uuid4())
        payment_params = {
            "quickpay-form": "shop",
            "paymentType": "AC",
            "targets": f"Оплата подписки для user_id={user_id}",
            "sum": 2.00,
            "label": payment_label,
            "receiver": YOOMONEY_WALLET,
            "successURL": f"https://t.me/{(await bot.get_me()).username}"
        }
        payment_url = f"https://yoomoney.ru/quickpay/confirm.xml?{urlencode(payment_params)}"
       
        # Сохранение label:user_id локально
        conn = sqlite3.connect("payments.db")
        c = conn.cursor()
        c.execute("INSERT INTO payments (label, user_id, status) VALUES (?, ?, ?)",
                  (payment_label, user_id, "pending"))
        conn.commit()
        conn.close()
       
        # Отправка label:user_id на Koyeb
        async with ClientSession() as session:
            try:
                async with session.post(KOYEB_URL, json={"label": payment_label, "user_id": user_id}) as response:
                    if response.status == 200:
                        logger.info(f"label={payment_label} отправлен на Koyeb для user_id={user_id}")
                    else:
                        logger.error(f"Ошибка отправки на Koyeb: {await response.text()}")
                        await bot.send_message(chat_id, "Ошибка сервера, попробуйте позже.")
                        return
            except Exception as e:
                logger.error(f"Ошибка связи с Koyeb: {e}")
                await bot.send_message(chat_id, "Ошибка сервера, попробуйте позже.")
                return
       
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton(text="Оплатить", url=payment_url))
        await bot.send_message(chat_id, "Перейдите по ссылке для оплаты 2 рублей:", reply_markup=keyboard)
        logger.info(f"Отправлена ссылка на оплату для user_id={user_id}, label={payment_label}")
    except Exception as e:
        logger.error(f"Ошибка в обработчике /pay: {e}")
        await bot.send_message(chat_id, "Произошла ошибка при создании платежа, попробуйте позже.")

# Обработчик пинга для UptimeRobot
async def handle_ping(request):
    logger.info("Получен GET-запрос на /ping")
    return web.Response(text="Bot is alive", status=200)

# Веб-сервер для webhook
async def on_startup(_):
    logger.info(f"Попытка установки webhook: {WEBHOOK_URL}")
    try:
        await bot.delete_webhook()
        await bot.set_webhook(WEBHOOK_URL)
        logger.info(f"Webhook успешно установлен: {WEBHOOK_URL}")
    except Exception as e:
        logger.error(f"Ошибка установки webhook: {e}\n{traceback.format_exc()}")
        sys.exit(1)

async def on_shutdown(_):
    logger.info("Удаление webhook")
    try:
        await bot.delete_webhook()
        await dp.storage.close()
        await dp.storage.wait_closed()
        await bot.session.close()
    except Exception as e:
        logger.error(f"Ошибка при удалении webhook: {e}")

async def handle_webhook(request):
    try:
        update = await request.json()
        logger.info("Получено обновление от Telegram")
        Bot.set_current(bot)
        Dispatcher.set_current(dp)
        await dp.process_update(types.Update(**update))
        return web.Response(status=200)
    except Exception as e:
        logger.error(f"Ошибка обработки webhook: {e}\n{traceback.format_exc()}")
        return web.Response(status=500)

# Настройка веб-сервера
app = web.Application()
app.router.add_post(WEBHOOK_PATH, handle_webhook)
app.router.add_get("/ping", handle_ping)
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == "__main__":
    logger.info("Запуск веб-сервера для webhook")
    try:
        port = 8080  # Жёстко задаём порт 8080
        logger.info(f"Запуск сервера на порту {port}")
        web.run_app(app, host="0.0.0.0", port=port)
    except Exception as e:
        logger.error(f"Ошибка запуска веб-сервера: {e}\n{traceback.format_exc()}")
        sys.exit(1)

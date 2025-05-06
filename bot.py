import logging
import sys
import uuid
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import ClientSession
from urllib.parse import urlencode
import traceback
import asyncio
import sqlite3

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

# Инициализация бота
logger.info("Попытка инициализации бота")
try:
    bot = Bot(token=TOKEN)
    logger.info("Бот успешно инициализирован")
except Exception as e:
    logger.error(f"Ошибка инициализации бота: {e}")
    sys.exit(1)

storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
logger.info("Диспетчер инициализирован")

# Инициализация SQLite (локальная база для бота)
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
            "sum": 2.00,  # Изменено на 2 рубля
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
            except Exception as e:
                logger.error(f"Ошибка связи с Koyeb: {e}")
       
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton(text="Оплатить", url=payment_url))
        await bot.send_message(chat_id, "Перейдите по ссылке для оплаты 2 рублей:", reply_markup=keyboard)
        logger.info(f"Отправлена ссылка на оплату для user_id={user_id}, label={payment_label}")
    except Exception as e:
        logger.error(f"Ошибка в обработчике /pay: {e}")
        await bot.send_message(chat_id, "Произошла ошибка при создании платежа, попробуйте позже.")

# Запуск бота с повторными попытками
async def start_polling_with_retries():
    logger.info("Запуск polling с повторными попытками")
    attempt = 1
    while True:
        try:
            logger.info(f"Попытка {attempt}: Пропуск старых обновлений")
            await dp.skip_updates()
            logger.info(f"Попытка {attempt}: Запуск polling")
            await dp.start_polling(timeout=20)
            logger.info("Polling успешно запущен")
            break
        except Exception as e:
            logger.error(f"Попытка {attempt}: Ошибка запуска polling: {e}\n{traceback.format_exc()}")
            logger.info("Повторная попытка через 5 секунд...")
            await asyncio.sleep(5)
            attempt += 1
            if attempt > 5:
                logger.error("Превышено количество попыток запуска polling")
                raise Exception("Не удалось запустить polling после 5 попыток")

async def on_startup(_):
    logger.info("Вызов on_startup")
    return True

if __name__ == "__main__":
    logger.info("Инициализация главного цикла")
    try:
        asyncio.run(start_polling_with_retries())
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске: {e}\n{traceback.format_exc()}")
        sys.exit(1)

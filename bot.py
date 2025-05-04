import logging
import sys
import uuid
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
from urllib.parse import urlencode
import traceback

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)
logger.info("Начало выполнения скрипта")

# Настройки
TOKEN = "7241683107:AAEG6RCRM4Ar1sDYpTV8BsaHfGUj2WXobhI"  # Замени на токен от @BotFather
YOOMONEY_WALLET = "your_wallet_number"  # Замени на номер кошелька YooMoney (41001...)
YOOMONEY_SECRET = "your_notification_secret"  # Замени на секрет для уведомлений

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
            "Стоимость: 500.00 🇷🇺RUB\n"
            "Срок действия: 1 месяц\n\n"
            "Вы получите доступ к следующим ресурсам:\n"
            "• Мой кайф (канал)"
        )
        await message.answer(welcome_text, reply_markup=keyboard)
        logger.info(f"Отправлен ответ на /start для user_id={user_id}")
    except Exception as e:
        logger.error(f"Ошибка в обработчике /start: {e}")
        await message.answer("Произошла ошибка, попробуйте позже.")

# Обработчик команды /help
@dp.message_handler(commands=['help'])
async def help_command(message: types.Message):
    try:
        user_id = str(message.from_user.id)
        logger.info(f"Получена команда /help от user_id={user_id}")
        help_text = (
            "Доступные команды:\n"
            "/start - Начать и получить ссылку на оплату\n"
            "/help - Показать эту помощь\n"
            "/info - Информация о боте\n"
            "/pay - Создать платёж"
        )
        await message.answer(help_text)
        logger.info(f"Отправлен ответ на /help для user_id={user_id}")
    except Exception as e:
        logger.error(f"Ошибка в обработчике /help: {e}")
        await message.answer("Произошла ошибка, попробуйте позже.")

# Обработчик команды /info
@dp.message_handler(commands=['info'])
async def info_command(message: types.Message):
    try:
        user_id = str(message.from_user.id)
        logger.info(f"Получена команда /info от user_id={user_id}")
        info_text = "Это бот для подписки на канал 'Мой кайф'. Используйте /start или /pay для оплаты."
        await message.answer(info_text)
        logger.info(f"Отправлен ответ на /info для user_id={user_id}")
    except Exception as e:
        logger.error(f"Ошибка в обработчике /info: {e}")
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
            "sum": 500.00,
            "label": payment_label,
            "receiver": YOOMONEY_WALLET,
            "successURL": "https://t.me/your_bot_username"  # Замени на ссылку на бота
        }
        payment_url = f"https://yoomoney.ru/quickpay/confirm.xml?{urlencode(payment_params)}"
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton(text="Оплатить", url=payment_url))
        await bot.send_message(chat_id, "Перейдите по ссылке для оплаты:", reply_markup=keyboard)
        logger.info(f"Отправлена ссылка на оплату для user_id={user_id}, label={payment_label}")
    except Exception as e:
        logger.error(f"Ошибка в обработчике /pay: {e}")
        await bot.send_message(chat_id, "Произошла ошибка при создании платежа, попробуйте позже.")

# Запуск бота
async def on_shutdown(dp):
    logger.info("Начало процедуры завершения бота")
    try:
        await dp.bot.close()
        logger.info("Бот успешно закрыт")
    except Exception as e:
        logger.error(f"Ошибка при завершении: {e}")

def on_startup(_):
    logger.info("Бот запущен")

if __name__ == "__main__":
    logger.info("Запуск polling")
    try:
        executor.start_polling(dp, skip_updates=True, on_startup=on_startup, on_shutdown=on_shutdown)
    except Exception as e:
        logger.error(f"Критическая ошибка запуска polling: {e}\n{traceback.format_exc()}")
        sys.exit(1)

# bot.py

import telebot
from telebot import types
import config
import logging
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота
bot = telebot.TeleBot(config.TELEGRAM_BOT_TOKEN)

# Области доступа для Google Sheets API
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# Загрузка учетных данных Google API
creds = Credentials.from_service_account_file(config.GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)

# Список товаров
products = [
    {'id': 1, 'name': 'Цифровой товар 1', 'price': 100},
    {'id': 2, 'name': 'Цифровой товар 2', 'price': 200},
    # Добавьте больше товаров по необходимости
]

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(
        message.chat.id,
        "Добро пожаловать в наш магазин цифровых товаров!"
    )
    show_products_menu(message.chat.id)

# Функция для отображения списка товаров
def show_products_menu(chat_id):
    keyboard = types.InlineKeyboardMarkup()
    for product in products:
        button = types.InlineKeyboardButton(
            text=f"{product['name']} - {product['price']}₽",
            callback_data=f"buy_{product['id']}"
        )
        keyboard.add(button)
    bot.send_message(chat_id, "Выберите товар для покупки:", reply_markup=keyboard)

# Обработчик нажатий на кнопки
@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def handle_buy(call):
    product_id = int(call.data.split('_')[1])
    product = next((p for p in products if p['id'] == product_id), None)
    if product:
        prices = [types.LabeledPrice(label=product['name'], amount=product['price'] * 100)]
        bot.send_invoice(
            chat_id=call.message.chat.id,
            title=product['name'],
            description=f"Покупка {product['name']}",
            invoice_payload=f"payload_{product['id']}",
            provider_token=config.PAYMENT_PROVIDER_TOKEN,
            currency='RUB',
            prices=prices,
            start_parameter='purchase'
        )
    else:
        bot.answer_callback_query(call.id, "Товар не найден.")

# Обработчик перед подтверждением оплаты
@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

# Обработчик успешной оплаты
@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    logging.info(f"Получена оплата от {message.from_user.id}")
    product_code = get_product_code()
    if product_code:
        bot.send_message(message.chat.id, f"Спасибо за покупку! Ваш код товара: {product_code}")
    else:
        bot.send_message(message.chat.id, "Извините, товары закончились.")

# Функция для получения кода товара из Google Таблицы
def get_product_code():
    try:
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=config.GOOGLE_SHEET_ID, range='A1:A1').execute()
        values = result.get('values', [])
        if values:
            product_code = values[0][0]
            # Удаляем использованный код из таблицы
            sheet.batchUpdate(
                spreadsheetId=config.GOOGLE_SHEET_ID,
                body={
                    'requests': [
                        {
                            'deleteRange': {
                                'range': {
                                    'sheetId': get_sheet_id(),
                                    'startRowIndex': 0,
                                    'endRowIndex': 1
                                },
                                'shiftDimension': 'ROWS'
                            }
                        }
                    ]
                }
            ).execute()
            return product_code
        else:
            return None
    except Exception as e:
        logging.error(f"Ошибка при получении кода товара: {e}")
        return None

# Функция для получения sheetId
def get_sheet_id():
    try:
        spreadsheet = service.spreadsheets().get(spreadsheetId=config.GOOGLE_SHEET_ID).execute()
        sheet = spreadsheet['sheets'][0]
        sheet_id = sheet['properties']['sheetId']
        return sheet_id
    except Exception as e:
        logging.error(f"Ошибка при получении sheetId: {e}")
        return 0  # По умолчанию возвращаем 0

# Запуск бота
if __name__ == '__main__':
    bot.infinity_polling()

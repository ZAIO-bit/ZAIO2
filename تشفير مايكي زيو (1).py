import base64
import os
import telebot
from telebot import types

token = '7374830859:AAFu6YScUNurthqBjFhd8-JtWtYUwagh8Ck'
bot = telebot.TeleBot(token)

@bot.message_handler(commands=['start'])
def start(message):
    id = message.chat.id
    name = message.chat.first_name
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    y = types.InlineKeyboardButton(text='تشفير ملف 🗂', callback_data='encrypt')
    yy = types.InlineKeyboardButton(text='قناة المطور 🤖', url='https://t.me/zr63yr')
    keyboard.add(y, yy)
    bot.reply_to(
        message,
        f"مرحبا {name} في بوت تشفير ملفات نينجا 🗂⚙️",
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: True)
def callback_data(call):
    if call.data == 'encrypt':
        bot.send_message(call.message.chat.id, "أرسل الملف الذي تريد تشفيره الآن 🗂")


@bot.message_handler(content_types=['document'])
def handle_file(message):
    try:
        
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        original_file_name = message.document.file_name

        
        with open(original_file_name, 'wb') as file:
            file.write(downloaded_file)
        
        with open(original_file_name, 'rb') as f:
            file_content = f.read()
       
        encoded_content = base64.b64encode(file_content).decode()

        encrypted_content = f"""#تـم الـتـشـفـيـر بـواسـطـة زيو • 🗽 
# @c8s8sx
A = '.ninjapy'
import os, sys, base64 as B
C = '{encoded_content}'
try:
    with open(A, 'wb') as D: D.write(B.b64decode(C))
    os.system('python3 .ninjapy' + ' '.join(sys.argv[1:]))
except Exception as E: print(E)
finally:
    if os.path.exists(A): os.remove(A)
"""

        
        encrypted_file_name = "ninja_" + original_file_name
        with open(encrypted_file_name, 'w') as enc_file:
            enc_file.write(encrypted_content)

        with open(encrypted_file_name, 'rb') as enc_file:
            bot.send_document(message.chat.id, enc_file)

        os.remove(original_file_name)
        os.remove(encrypted_file_name)

        bot.send_message(message.chat.id, "تم التشفير ولاتنسى تدخل القناه🌚🤎✅")
    except Exception as e:
        bot.send_message(message.chat.id, f"حدث خطأ أثناء التشفير: {e}")

bot.polling()
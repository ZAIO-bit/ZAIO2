import base64
import os
import telebot
from telebot import types

token = '7374830859:AAG8CLXeahwPw9V0dXjW5Wm8qED9hARKwNA'
bot = telebot.TeleBot(token)

@bot.message_handler(commands=['start'\])
def start(message):
    id = message.chat.id
    name = message.chat.first_name
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    y = types.InlineKeyboardButton(text='تشفير ملف 🗂', callback_data='encrypt')
    y2 = types.InlineKeyboardButton(text='فك تشفير ملف 🔓', callback_data='decrypt')
    yy = types.InlineKeyboardButton(text='قناة المطور 🤖', url='https://t.me/+t4VLDtL1iGU0NzEy')
    keyboard.add(y, y2, yy)
    bot.reply_to(
        message,
        f"مرحبا \{name\} في بوت تشفير/فك تشفير ملفات نينجا 🗂⚙️\n\n"
        "🔥 المطور: @c8s8sx - 𝒁𝑨𝑰𝑶",
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: True)
def callback_data(call):
    if call.data == 'encrypt':
        bot.send_message(call.message.chat.id, "أرسل الملف الذي تريد تشفيره الآن 🗂")
    elif call.data == 'decrypt':
        bot.send_message(call.message.chat.id, "أرسل الملف المشفر الذي تريد فك تشفيره الآن 🔓")

@bot.message_handler(content_types=['document'\])
def handle_file(message):
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        original_file_name = message.document.file_name

        if original_file_name.startswith('ninja_'):
            # منع فك تشفير الملفات المشفرة داخل البوت
            with open('temp_file', 'wb') as file:
                file.write(downloaded_file)
            
            with open('temp_file', 'r') as f:
                file_content = f.read()
            
            if '# @c8s8sx' in file_content:  # هذا يعني أن الملف مشفر داخل البوت
                os.remove('temp_file')
                bot.send_message(message.chat.id, "⚠️ لا يمكن فك تشفير الملفات المشفرة داخل هذا البوت")
                return
            
            # عملية فك التشفير للملفات الخارجية
            start_idx = file_content.find("C = '") + 5
            end_idx = file_content.find("'", start_idx)
            encoded_content = file_content[start_idx:end_idx\]
            
            decoded_content = base64.b64decode(encoded_content)
            
            decrypted_file_name = "decrypted_" + original_file_name[6:\]
            with open(decrypted_file_name, 'wb') as dec_file:
                dec_file.write(decoded_content)

            with open(decrypted_file_name, 'rb') as dec_file:
                bot.send_document(message.chat.id, dec_file)

            os.remove('temp_file')
            os.remove(decrypted_file_name)

            bot.send_message(message.chat.id, "تم فك التشفير بنجاح 🌚🤎✅\n\n🔥 المطور: @c8s8sx")
        
        else:
            # عملية التشفير الأصلية مع إضافة الحقوق
            with open(original_file_name, 'wb') as file:
                file.write(downloaded_file)
            
            with open(original_file_name, 'rb') as f:
                file_content = f.read()
           
            encoded_content = base64.b64encode(file_content).decode()

            encrypted_content = f"""#تـم الـتـشـفـيـر بـواسـطـة زيو • 🗽 
# @c8s8sx - 𝒁𝑨𝑰𝑶
A = '.ninjapy'
import os, sys, base64 as B
C = '\{encoded_content\}'
try:
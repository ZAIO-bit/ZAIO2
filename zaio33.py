import base64
import os
import telebot
from telebot import types

# توكن البوت (يجب استبداله بتوكنك الفعلي)
TOKEN = '7474087286:AAGNA2A_xebAvBzX5d2hBUCsYCQDnadk4bU'
bot = telebot.TeleBot(TOKEN)

# ━━━━━━━━━━ ✦ رد فعل أمر /start ━━━━━━━━━━
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    user_name = message.from_user.first_name
    
    # إنشاء زراوير داخلية
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    btn_encrypt = types.InlineKeyboardButton(text='تشفير ملف 🗂', callback_data='encrypt')
    btn_decrypt = types.InlineKeyboardButton(text='فك تشفير ملف 🔓', callback_data='decrypt')
    btn_channel = types.InlineKeyboardButton(text='قناة المطور 🤖', url='https://t.me/+t4VLDtL1iGU0NzEy')
    keyboard.add(btn_encrypt, btn_decrypt, btn_channel)
    
    # إرسال رسالة الترحيب
    welcome_msg = (
        f"مرحبًا {user_name} في بوت تشفير ملفات نينجا! 🗂⚙️\n\n"
        "🔥 المطور: @c8s8sx - 𝒁𝑨𝑰𝑶"
    )
    bot.send_message(user_id, welcome_msg, reply_markup=keyboard)

# ━━━━━━━━━━ ✦ رد فعل الأزرار ━━━━━━━━━━
@bot.callback_query_handler(func=lambda call: True)
def handle_buttons(call):
    if call.data == 'encrypt':
        bot.send_message(call.message.chat.id, "↯ أرسل الملف المراد تشفيره الآن...")
    elif call.data == 'decrypt':
        bot.send_message(call.message.chat.id, "↯ أرسل الملف المشفر لتفكيكه الآن...")

# ━━━━━━━━━━ ✦ معالجة الملفات المرسلة ━━━━━━━━━━
@bot.message_handler(content_types=['document'])
def process_file(message):
    try:
        # تنزيل الملف
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        file_name = message.document.file_name

        # حالة فك التشفير
        if file_name.startswith('ninja_'):
            with open('temp_file', 'wb') as f:
                f.write(downloaded_file)
            
            with open('temp_file', 'r', encoding='utf-8') as f:
                content = f.read()
            
            # منع فك تشفير ملفات البوت الداخلية
            if '# @c8s8sx' in content:
                os.remove('temp_file')
                bot.reply_to(message, "⛔ هذا الملف مشفر داخليًا ولا يمكن فك تشفيره هنا!")
                return
            
            # استخراج المحتوى المشفر
            start_idx = content.find("C = '") + 5
            end_idx = content.find("'", start_idx)
            encrypted_data = content[start_idx:end_idx]
            
            # فك التشفير
            decrypted_data = base64.b64decode(encrypted_data)
            output_name = f"decrypted_{file_name[6:]}"
            
            with open(output_name, 'wb') as f:
                f.write(decrypted_data)
            
            # إرسال الملف المفكوك
            with open(output_name, 'rb') as f:
                bot.send_document(message.chat.id, f)
            
            # تنظيف الملفات المؤقتة
            os.remove('temp_file')
            os.remove(output_name)
            bot.reply_to(message, "✓ تم فك التشفير بنجاح!\n\n🔰 المطور: @c8s8sx")

        # حالة التشفير
        else:
            # تشفير المحتوى
            encoded_data = base64.b64encode(downloaded_file).decode('utf-8')
            
            # إنشاء ملف الإخراج
            output_content = f"""# ملف مشفر بواسطة بوت نينجا
# @c8s8sx - 𝒁𝑨𝑰𝑶
import os, base64
data = '{encoded_data}'
decrypted = base64.b64decode(data)
with open('decrypted_{file_name}', 'wb') as f:
    f.write(decrypted)
os.system('python decrypted_{file_name}')"""
            
            # حفظ الملف المشفر
            output_name = f"ninja_{file_name}"
            with open(output_name, 'w', encoding='utf-8') as f:
                f.write(output_content)
            
            # إرسال الملف المشفر
            with open(output_name, 'rb') as f:
                bot.send_document(message.chat.id, f)
            
            # تنظيف الملفات
            os.remove(file_name)
            os.remove(output_name)
            bot.reply_to(message, "✓ تم التشفير بنجاح!\n\n🔰 المطور: @c8s8sx")

    except Exception as error:
        bot.reply_to(message, f"❌ حدث خطأ:\n{str(error)}")

# ━━━━━━━━━━ ✦ تشغيل البوت ━━━━━━━━━━
if __name__ == '__main__':
    print("~ البوت يعمل الآن!")
    bot.polling(none_stop=True)

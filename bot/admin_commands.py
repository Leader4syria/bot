import traceback
from telebot import types
from . import bot
from database import Session, User
from utils import is_admin, send_message_to_user, edit_message_text_and_markup, create_back_to_main_menu_inline_keyboard
import config


@bot.message_handler(commands=['id'])
def handle_id_command(message):
    chat_id = message.chat.id
    args = message.text.split()

    if len(args) != 2:
        bot.send_message(chat_id, "❌ صيغة الأمر غير صحيحة. الاستخدام الصحيح:\n<code>/id &lt;معرف_المستخدم&gt;</code>", parse_mode="HTML")
        return

    try:
        target_user_id = int(args[1])

        chat_link = f"tg://user?id={target_user_id}"

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💬 الدخول إلى المحادثة", url=chat_link))

        response_text = (
            f"🔗 <b>رابط المحادثة مع المستخدم:</b>\n"
            f"<blockquote>🆔 <b>المعرف:</b> <code>{target_user_id}</code></blockquote>\n"
            f"🔗 <b>الرابط:</b> <code>{chat_link}</code>\n\n"
            f"انقر على الزر أدناه للدخول إلى المحادثة مع هذا المستخدم:"
        )

        bot.send_message(chat_id, response_text, reply_markup=markup, parse_mode="HTML")

    except ValueError:
        bot.send_message(chat_id, "❌ معرف المستخدم غير صالح. يرجى إدخال رقم صحيح.", parse_mode="HTML")
    except Exception as e:
        print(f"خطأ في معالج /id: {e}")
        bot.send_message(chat_id, "❌ حدث خطأ أثناء معالجة الطلب. يرجى المحاولة مرة أخرى.", parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "show_admin_panel_info")
def show_admin_panel_info(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    info_text = (
        f"<b>لوحة تحكم المشرف:</b>\n"
        f"للوصول إلى لوحة تحكم المشرف، يرجى فتح الرابط التالي في متصفح الويب الخاص بك:\n"
        f"<code>http://localhost:{config.FLASK_PORT}/admin</code>\n\n"
        f"<b>ملاحظة هامة:</b> هذا الرابط يعمل فقط إذا كنت تقوم بتشغيل البوت ولوحة التحكم على نفس الجهاز.\n"
        f"عند نشر البوت، ستحتاج إلى استبدال <code>localhost</code> بعنوان IP عام أو اسم نطاق صالح."
    )
    edit_message_text_and_markup(chat_id, message_id, info_text, reply_markup=create_back_to_main_menu_inline_keyboard(), parse_mode="HTML")
    bot.answer_callback_query(call.id, "معلومات لوحة المشرف.")

@bot.message_handler(commands=['add'])
def handle_add_balance(message):
    chat_id = message.chat.id
    telegram_id = message.from_user.id

    if not is_admin(telegram_id):
        bot.send_message(chat_id, "عذرًا، هذا الأمر متاح للمشرفين فقط.", parse_mode="HTML")
        return

    args = message.text.split()
    if len(args) != 3:
        bot.send_message(chat_id, "صيغة الأمر غير صحيحة. الاستخدام الصحيح: <code>/add &lt;معرف_المستخدم&gt; &lt;المبلغ&gt;</code>", parse_mode="HTML")
        return

    s = Session()
    try:
        target_user_id = int(args[1])
        amount_to_add = float(args[2])

        if amount_to_add <= 0:
            bot.send_message(chat_id, "المبلغ يجب أن يكون رقمًا موجبًا.", parse_mode="HTML")
            s.close()
            return

        target_user = s.query(User).filter_by(telegram_id=target_user_id).first()

        if not target_user:
            bot.send_message(chat_id, f"لم يتم العثور على المستخدم بالمعرف <code>{target_user_id}</code>.", parse_mode="HTML")
            s.close()
            return

        original_balance = target_user.balance
        target_user.balance += amount_to_add
        s.commit()

        bot.send_message(chat_id,
                         f"✅ <b>تم إضافة ${amount_to_add:.2f} إلى رصيد المستخدم <code>{target_user.full_name or target_user.username}</code> (ID: <code>{target_user_id}</code>).</b>\n"
                         f"الرصيد السابق: ${original_balance:.2f}\n"
                         f"الرصيد الجديد: ${target_user.balance:.2f}",
                         parse_mode="HTML")

        send_message_to_user(target_user_id,
                             f"💰 <b>تم إضافة رصيد إلى حسابك!</b>\n"
                             f"تم إضافة مبلغ ${amount_to_add:.2f} إلى رصيدك.\n"
                             f"رصيدك الجديد هو: ${target_user.balance:.2f}",
                             parse_mode="HTML")

    except ValueError:
        bot.send_message(chat_id, "الرجاء إدخال معرف مستخدم صحيح ومبلغ رقمي صحيح.", parse_mode="HTML")
    except Exception as e:
        s.rollback()
        print(f"خطأ في معالج /add: {e}\n{traceback.format_exc()}")
        bot.send_message(chat_id, "حدث خطأ أثناء معالجة طلبك. يرجى المحاولة مرة أخرى.", parse_mode="HTML")
    finally:
        s.close()

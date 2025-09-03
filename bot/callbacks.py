import traceback
from telebot import types
from . import bot, user_states
from database import Session, User
from utils import edit_message_text_and_markup, get_or_create_user, delete_message
from config import START_MESSAGE, SUPPORT_CHANNEL_LINK
import config

def create_main_menu_inline_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("الخدمات 🛍️", callback_data="show_services_menu")
    )
    markup.add(
        types.InlineKeyboardButton("شحن الرصيد 💸", callback_data="show_recharge_options"),
        types.InlineKeyboardButton("معلوماتي 🪪 ", callback_data="show_my_balance")
    )
    markup.add(
        types.InlineKeyboardButton("طلباتي 📋", callback_data="show_my_orders"),
        types.InlineKeyboardButton("ربح اموال مجانا 👥", callback_data="show_referral_system"),
    )
    markup.add(
        types.InlineKeyboardButton("تواصل معنا 📞", url=config.SUPPORT_CHANNEL_LINK)
    )
    return markup

@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def callback_main_menu(call):
    try:
        chat_id = call.message.chat.id
        message_id = call.message.message_id
        s = Session()
        user = s.query(User).filter_by(telegram_id=call.from_user.id).first()
        s.close()

        if user:
            welcome_message_text = (
            f"{START_MESSAGE}\n\n"
            f"<blockquote><b>معرفك:</b> <code>{user.telegram_id}</code></blockquote>\n"
            f"<blockquote><b>رصيدك:</b> ${user.balance:.2f}</blockquote>\n"
            f"<b>اختر من الأزرار :</b>"
        )
            edit_message_text_and_markup(chat_id, message_id, welcome_message_text, reply_markup=create_main_menu_inline_keyboard(), parse_mode="HTML")
            bot.answer_callback_query(call.id, "تم الرجوع إلى القائمة الرئيسية.")
        else:
            bot.send_message(chat_id, "لم يتم العثور على معلومات حسابك. يرجى استخدام أمر /start أولاً.", parse_mode="HTML")
            bot.answer_callback_query(call.id, "المستخدم غير موجود. يرجى البدء.", show_alert=True)
    except Exception as e:
        print(f"خطأ في callback_main_menu: {e}\n{traceback.format_exc()}")
        bot.answer_callback_query(call.id, "حدث خطأ. يرجى المحاولة مرة أخرى.", show_alert=True)

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    chat_id = message.chat.id
    telegram_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name

    if user_states.get(chat_id, {}).get("state") is None:
        s = Session()
        try:
            user, is_new_user = get_or_create_user(telegram_id, username, full_name, session=s)

            if chat_id in user_states and "main_menu_message_id" in user_states[chat_id]:
                delete_message(chat_id, user_states[chat_id]["main_menu_message_id"])

            welcome_message_text = (
    f"{START_MESSAGE}\n\n"
    f"<blockquote><b>معرفك:</b> <code>{user.telegram_id}</code></blockquote>\n"
    f"<blockquote><b>رصيدك:</b> ${user.balance:.2f}</blockquote>\n"
    f"<b>اختر من الأزرار :</b>"
)
            sent_message = bot.send_message(chat_id, welcome_message_text, reply_markup=create_main_menu_inline_keyboard(), parse_mode="HTML")
            user_states[chat_id] = {"main_menu_message_id": sent_message.message_id}
        except Exception as e:
            print(f"خطأ في معالج الرسائل العام: {e}")
            bot.send_message(chat_id, "حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى لاحقًا.")
        finally:
            s.close()
    else:
        pass

import requests
import random
import string
from database import User, Category, Service, Order, Payment, Withdrawal, Session
from config import ADMIN_IDS, BOT_TOKEN, REFERRAL_BONUS_AMOUNT, REFERRAL_COUNT_FOR_BONUS, MIN_REFERRAL_WITHDRAWAL_AMOUNT
from telebot import TeleBot, types
from sqlalchemy.exc import IntegrityError
import config

bot = TeleBot(BOT_TOKEN)

def send_pushbullet_notification(title, body):
    try:
        headers = {
            'Access-Token': config.PUSHBULLET_API_KEY,
            'Content-Type': 'application/json'
        }
        data = {
            'type': 'note',
            'title': title,
            'body': body
        }
        response = requests.post('https://api.pushbullet.com/v2/pushes',
                               headers=headers,
                               json=data)
        return response.status_code == 200
    except Exception as e:
        print(f"فشل إرسال إشعار Pushbullet: {e}")
        return False

def generate_referral_code(length=8):
    characters = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(random.choice(characters) for i in range(length))
        s = Session()
        existing_user = s.query(User).filter_by(referral_code=code).first()
        s.close()
        if not existing_user:
            return code

def get_or_create_user(telegram_id, username, full_name, referrer_id=None, session=None):
    should_close_session = False
    if session is None:
        session = Session()
        should_close_session = True

    user = session.query(User).filter_by(telegram_id=telegram_id).first()
    is_new_user = False

    if not user:
        is_new_user = True
        referral_code = generate_referral_code()
        user = User(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
            referral_code=referral_code,
            referrer_id=referrer_id
        )
        if telegram_id in ADMIN_IDS:
            user.is_admin = True
        session.add(user)
        try:
            session.commit()
            print(f"تم إنشاء مستخدم جديد: {user.username} (ID: {user.telegram_id})")

            if referrer_id:
                referrer = session.query(User).filter_by(telegram_id=referrer_id).first()
                if referrer:
                    referrer.referred_users_count += 1

                    referrer.referral_balance += REFERRAL_BONUS_AMOUNT

                    print(f"تم تحديث عدد الإحالات للمحيل {referrer.username}: {referrer.referred_users_count}")
                    print(f"تم إضافة مكافأة إحالة ${REFERRAL_BONUS_AMOUNT:.2f} للمحيل {referrer.username}. رصيد الإحالة الجديد: {referrer.referral_balance}")

                    send_message_to_user(
                        referrer.telegram_id,
                        f"<b>تهانينا!</b> لقد انضم مستخدم جديد ({full_name}) عبر رابط الإحالة الخاص بك.\n"
                        f"تم إضافة ${REFERRAL_BONUS_AMOUNT:.2f} إلى رصيد الإحالة الخاص بك.\n"
                        f"رصيد الإحالة الجديد: ${referrer.referral_balance:.2f}\n"
                        f"عدد الإحالات الإجمالي: {referrer.referred_users_count}",
                        parse_mode="HTML"
                    )

                    session.commit()

        except IntegrityError:
            session.rollback()
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            is_new_user = False
        except Exception as e:
            session.rollback()
            print(f"خطأ في get_or_create_user: {e}")
            is_new_user = False

    if should_close_session:
        session.close()
    return user, is_new_user

def is_admin(telegram_id):
    s = Session()
    user = s.query(User).filter_by(telegram_id=telegram_id).first()
    s.close()
    return user and user.is_admin

def create_pagination_keyboard(current_page, total_pages, prefix):
    keyboard = types.InlineKeyboardMarkup()
    buttons = []
    if current_page > 1:
        buttons.append(types.InlineKeyboardButton("⬅️ السابق", callback_data=f"{prefix}_page_{current_page - 1}"))
    buttons.append(types.InlineKeyboardButton(f"الصفحة {current_page}/{total_pages}", callback_data="ignore"))
    if current_page < total_pages:
        buttons.append(types.InlineKeyboardButton("التالي ➡️", callback_data=f"{prefix}_page_{current_page + 1}"))
    keyboard.add(*buttons)
    return keyboard

def create_categories_keyboard(categories, back_button_data=None):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    for cat in categories:
        keyboard.add(types.InlineKeyboardButton(cat.name, callback_data=f"cat_{cat.id}"))
    if back_button_data:
        keyboard.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=back_button_data))
    return keyboard

def create_services_keyboard(services, category_id, back_button_data=None):
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    for service in services:
        keyboard.add(types.InlineKeyboardButton(
            f"{service.name} | ${service.base_price:.2f} لكل {service.base_quantity} ✅",
            callback_data=f"service_{service.id}"
        ))
    if back_button_data:
        keyboard.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=back_button_data))
    return keyboard

def send_message_to_user(chat_id, text, **kwargs):
    try:
        bot.send_message(chat_id, text, **kwargs)
        return True
    except Exception as e:
        print(f"فشل إرسال الرسالة إلى {chat_id}: {e}")
        return False

def delete_message(chat_id, message_id):
    try:
        bot.delete_message(chat_id, message_id)
    except Exception as e:
        print(f"فشل حذف الرسالة {message_id} في الدردشة {chat_id}: {e}")

def edit_message_text_and_markup(chat_id, message_id, text, **kwargs):
    try:
        bot.edit_message_text(text, chat_id, message_id, **kwargs)
    except Exception as e:
        print(f"فشل تعديل الرسالة {message_id} في الدردشة {chat_id}: {e}")

def send_subscription_message(chat_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("اضغط هنا للاشتراك", url=config.MANDATORY_CHANNEL_LINK))
    markup.add(types.InlineKeyboardButton("✅ لقد اشتركت", callback_data="check_subscription"))
    bot.send_message(chat_id, "عذراً، يجب عليك الاشتراك في قناة البوت أولاً لاستخدامه.", reply_markup=markup)

def is_user_subscribed(user_id):
    """
    Checks if a user is a member of the mandatory channel.
    """
    try:
        member = bot.get_chat_member(config.MANDATORY_CHANNEL_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        print(f"Error checking subscription for user {user_id}: {e}")
        return False

def create_back_to_main_menu_inline_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu"))
    return markup

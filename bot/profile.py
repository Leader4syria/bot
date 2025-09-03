from telebot import types
from . import bot
from database import Session, User, Order, PaymentMethod
from utils import edit_message_text_and_markup, create_back_to_main_menu_inline_keyboard, is_user_subscribed, send_subscription_message
from sqlalchemy.orm import joinedload
import config

@bot.callback_query_handler(func=lambda call: call.data == "show_recharge_options")
def show_recharge_options(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    if not is_user_subscribed(user_id):
        send_subscription_message(chat_id)
        bot.answer_callback_query(call.id)
        return

    message_id = call.message.message_id

    s = Session()
    payment_methods = s.query(PaymentMethod).filter_by(is_available=True).all()
    s.close()

    markup = types.InlineKeyboardMarkup(row_width=1)

    if payment_methods:
        for method in payment_methods:
            btn_text = f"{method.name}"
            if method.contact_user:
                btn_text += f" (@{method.contact_user})"
            markup.add(types.InlineKeyboardButton(btn_text, url=f"https://t.me/{method.contact_user.lstrip('@')}"))
    else:
        pass

    markup.add(types.InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu"))

    message_text = (
    "• مرحبا بك عزيزي في قسم شحن الرصيد 𓃵 🌴\n"
    "----------------------------\n"
    "💰 ادنى حد للشحن: 1$\n"
    "💰 اقصى حد للشحن: 500$\n"
    "----------------------------\n"
    "» نستقبل الدفع عبر الطرق التالية 👇🏽 •\n\n"

    "<blockquote>🇸🇾 سوريا:\n"
    "» 1- شام كاش\n"
    "» 2- سيريتل كاش\n"
    "» 3- بينانس\n"
    "» 4- بايير\n"
    "« 5- نقبل جميع العملات الرقمية</blockquote>\n\n"

    "<blockquote>💲 عملات رقمية:\n"
    "» 6- USDT</blockquote>\n\n"

    "<blockquote>🇮🇶 العراق:\n"
    "» 7- كارتات اسياسيل • زين كاش</blockquote>\n\n"

    "<blockquote>🇪🇬 مصر:\n"
    "» 8- فودافون كاش • انستا باي</blockquote>\n\n"

    "<blockquote>🇸🇦 السعودية:\n"
    "» 9- بطاقة سوا • راجحي</blockquote>\n\n"

    "<blockquote>🇯🇴 الأردن:\n"
    "» 10- اورانج موني • كليك بنك الأردن</blockquote>\n\n"

    "<blockquote>🇱🇧 لبنان:\n"
    "» 11- ويش موني</blockquote>\n\n"

    "<blockquote>🇹🇷 تركيا:\n"
    "» 12- بابارا • تحويل بنكي • زراعات\n"
    "⚡🔥 تواصل دولار | جميع طرق الدفع داخل تركيا</blockquote>\n\n"

    "----------------------------\n"
    "📩 ان لم تجد طريقة دفع مناسبة، تواصل معنا لتوفيرها.\n\n"
    "» لشحن الرصيد تواصل عبر المعرف 👇🏿\n\n"
    "👉 https://t.me/AleepoMarket"
)


    edit_message_text_and_markup(chat_id, message_id, message_text, reply_markup=markup, parse_mode="HTML")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "show_my_balance")
def show_my_balance(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    if not is_user_subscribed(user_id):
        send_subscription_message(chat_id)
        bot.answer_callback_query(call.id)
        return

    message_id = call.message.message_id
    telegram_id = call.from_user.id
    s = Session()
    user = s.query(User).options(joinedload(User.referred_users)).filter_by(telegram_id=telegram_id).first()
    s.close()

    if user:
        referred_count = user.referred_users_count if user.referred_users_count is not None else 0
        info_text = (
            f"<blockquote><b>معلومات حسابك:</b></blockquote>\n"
            f"<blockquote>👤 <b>الاسم:</b> {user.full_name or 'غير متوفر'}</blockquote>\n"
            f"<blockquote>🆔 <b>معرف تليجرام:</b> <code>{user.telegram_id}</code></blockquote>\n"
            f"<blockquote>💰 <b>رصيدك الأساسي:</b> ${user.balance:.2f}</blockquote>\n"
            f"<blockquote>💰 <b>رصيد الإحالة:</b> ${user.referral_balance:.2f}</blockquote>\n"
            f"<blockquote>🔗 <b>كود الإحالة الخاص بك:</b> <code>{user.referral_code}</code></blockquote>\n"
            f"<blockquote>👥 <b>عدد الأشخاص الذين أحلتهم:</b> {referred_count}</blockquote>"
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu"))
        edit_message_text_and_markup(chat_id, message_id, info_text, reply_markup=markup, parse_mode="HTML")
    else:
        edit_message_text_and_markup(chat_id, message_id, "لم يتم العثور على معلومات حسابك. يرجى استخدام أمر /start أولاً.", reply_markup=create_back_to_main_menu_inline_keyboard(), parse_mode="HTML")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "show_my_orders")
def show_my_orders(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    if not is_user_subscribed(user_id):
        send_subscription_message(chat_id)
        bot.answer_callback_query(call.id)
        return

    message_id = call.message.message_id
    telegram_id = call.from_user.id
    s = Session()
    orders = s.query(Order).options(joinedload(Order.service)).filter_by(user_id=telegram_id).order_by(Order.ordered_at.desc()).all()
    s.close()

    if not orders:
        edit_message_text_and_markup(chat_id, message_id, "لم تقم بتقديم أي طلبات بعد.", reply_markup=create_back_to_main_menu_inline_keyboard(), parse_mode="HTML")
        bot.answer_callback_query(call.id)
        return

    orders_text = "<b>قائمة طلباتك:</b>\n\n"
    for order in orders:
        status_emoji = "⏳"
        if order.status == "Completed":
            status_emoji = "✅"
        elif order.status == "Cancelled":
            status_emoji = "❌"

        orders_text += (
            f"<blockquote>"
            f"📦 <b>الطلب رقم:</b> <code>{order.id}</code>\n"
            f"✨ <b>الخدمة:</b> {order.service.name}\n"
            f"🔢 <b>الكمية:</b> {order.quantity}\n"
            f"💲 <b>السعر:</b> ${order.total_price:.2f}\n"
            f"🔗 <b>الرابط/المعرف:</b> <code>{order.link_or_id}</code>\n"
            f"📊 <b>الحالة:</b> {status_emoji} {order.status}\n"
            f"📅 <b>تاريخ الطلب:</b> {order.ordered_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"-----------------------------------------"
            f"</blockquote>\n"
        )
    edit_message_text_and_markup(chat_id, message_id, orders_text, reply_markup=create_back_to_main_menu_inline_keyboard(), parse_mode="HTML")
    bot.answer_callback_query(call.id)

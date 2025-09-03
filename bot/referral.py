import traceback
from telebot import types
from . import bot, user_states
from database import Session, User, Withdrawal
from utils import edit_message_text_and_markup, delete_message, create_back_to_main_menu_inline_keyboard
from sqlalchemy.orm import joinedload
from datetime import datetime
from config import MIN_REFERRAL_WITHDRAWAL_AMOUNT, REFERRAL_BONUS_AMOUNT, REFERRAL_COUNT_FOR_BONUS, ADMIN_IDS

@bot.callback_query_handler(func=lambda call: call.data == "show_referral_system")
def show_referral_system(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    telegram_id = call.from_user.id
    s = Session()
    user = s.query(User).options(joinedload(User.referred_users)).filter_by(telegram_id=telegram_id).first()

    if user:
        bot_info = bot.get_me()
        bot_username = bot_info.username if bot_info else "your_bot_username"
        referral_link = f"https://t.me/{bot_username}?start={user.referral_code}"

        referred_count = user.referred_users_count if user.referred_users_count is not None else 0

        potential_earnings = referred_count * REFERRAL_BONUS_AMOUNT
        next_bonus = (REFERRAL_COUNT_FOR_BONUS - (referred_count % REFERRAL_COUNT_FOR_BONUS)) if referred_count % REFERRAL_COUNT_FOR_BONUS != 0 else 0

        info_text = (
            f"<b>ربح المال عن طريق دعوة الأشخاص:</b>\n"
            f"ادعُ أصدقائك للانضمام إلى البوت الخاص بنا واكسب المال!\n\n"
            f"<blockquote>💰 <b>تحصل على ${REFERRAL_BONUS_AMOUNT:.2f} لكل شخص يدخل عبر رابطك</b></blockquote>\n"
            f"<blockquote>🎉 <b>كل {REFERRAL_COUNT_FOR_BONUS} إحالة تكسبك ${REFERRAL_COUNT_FOR_BONUS * REFERRAL_BONUS_AMOUNT:.2f}</b></blockquote>\n\n"
            f"<blockquote>🔗 <b>رابط الإحالة الخاص بك:</b>\n<code>{referral_link}</code></blockquote>\n\n"
            f"<blockquote>👥 <b>عدد الأشخاص الذين أحلتهم:</b> {referred_count}</blockquote>\n"
            f"<blockquote>💰 <b>إجمالي أرباح الإحالة:</b> ${potential_earnings:.2f}</blockquote>\n"
            f"<blockquote>💸 <b>رصيد الإحالة الحالي:</b> ${user.referral_balance:.2f}</blockquote>\n"
            f"<blockquote>📈 <b>متبقي {next_bonus} إحالة لتحصل على ${REFERRAL_BONUS_AMOUNT * next_bonus:.2f} إضافية</b></blockquote>\n"
            f"<blockquote>💳 <b>الحد الأدنى لسحب رصيد الإحالة:</b> ${MIN_REFERRAL_WITHDRAWAL_AMOUNT:.2f}</blockquote>"
        )

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("شارك رابط الإحالة", switch_inline_query=f"انضم إلى متجر الخدمات الرقمية عبر رابط الإحالة الخاص بي: {referral_link}"))
        markup.add(types.InlineKeyboardButton("سحب رصيد الإحالة 💸", callback_data="request_referral_withdrawal"))
        markup.add(types.InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu"))
        edit_message_text_and_markup(chat_id, message_id, info_text, reply_markup=markup, parse_mode="HTML")
    else:
        edit_message_text_and_markup(chat_id, message_id, "يرجى استخدام أمر /start أولاً للحصول على رابط الإحالة الخاص بك.", reply_markup=create_back_to_main_menu_inline_keyboard(), parse_mode="HTML")
    s.close()
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "request_referral_withdrawal")
def request_referral_withdrawal(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    telegram_id = call.from_user.id

    s = Session()
    user = s.query(User).filter_by(telegram_id=telegram_id).first()
    s.close()

    if not user:
        edit_message_text_and_markup(chat_id, message_id, "لم يتم العثور على معلومات حسابك. يرجى استخدام أمر /start أولاً.", reply_markup=create_back_to_main_menu_inline_keyboard(), parse_mode="HTML")
        bot.answer_callback_query(call.id)
        return

    if user.referral_balance < MIN_REFERRAL_WITHDRAWAL_AMOUNT:
        edit_message_text_and_markup(chat_id, message_id,
                                     f"عذرًا، رصيد الإحالة الخاص بك (${user.referral_balance:.2f}) أقل من الحد الأدنى للسحب (${MIN_REFERRAL_WITHDRAWAL_AMOUNT:.2f}).",
                                     reply_markup=create_back_to_main_menu_inline_keyboard(), parse_mode="HTML")
        bot.answer_callback_query(call.id, "رصيد إحالة غير كافٍ للسحب.", show_alert=True)
        return

    withdrawal_text = (
        f"<b>طلب سحب رصيد الإحالة:</b>\n"
        f"رصيد الإحالة الحالي: ${user.referral_balance:.2f}\n"
        f"الحد الأدنى للسحب: ${MIN_REFERRAL_WITHDRAWAL_AMOUNT:.2f}\n\n"
        f"الرجاء إدخال المبلغ الذي ترغب بسحبه من رصيد الإحالة (عدد صحيح أو عشري):"
    )
    edit_message_text_and_markup(chat_id, message_id, withdrawal_text, reply_markup=create_back_to_main_menu_inline_keyboard(), parse_mode="HTML")
    user_states[chat_id] = {"state": "waiting_referral_withdrawal_amount", "message_id": message_id}
    bot.answer_callback_query(call.id)


@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get("state") == "waiting_referral_withdrawal_amount")
def handle_withdrawal_amount_input(message):
    try:
        chat_id = message.chat.id
        telegram_id = message.from_user.id

        if user_states.get(chat_id, {}).get("state") != "waiting_referral_withdrawal_amount":
            bot.send_message(chat_id, "يبدو أن جلستك قد انتهت أو حدث خطأ. يرجى البدء من جديد باستخدام /start.", parse_mode="HTML")
            if chat_id in user_states:
                del user_states[chat_id]
            return

        state_info = user_states[chat_id]
        original_message_id = state_info["message_id"]

        try:
            amount = float(message.text)
            if amount <= 0:
                raise ValueError
        except ValueError:
            bot.send_message(chat_id, "مبلغ غير صالح. الرجاء إدخال عدد صحيح أو عشري موجب.", parse_mode="HTML")
            return

        s = Session()
        user = s.query(User).filter_by(telegram_id=telegram_id).first()
        s.close()

        if not user:
            bot.send_message(chat_id, "حدث خطأ. يرجى المحاولة مرة أخرى أو التواصل مع الدعم.", parse_mode="HTML")
            del user_states[chat_id]
            return

        min_amount = MIN_REFERRAL_WITHDRAWAL_AMOUNT
        current_balance = user.referral_balance
        balance_type_text = "رصيد الإحالة"

        if amount < min_amount:
            bot.send_message(chat_id,
                             f"المبلغ المطلوب (${amount:.2f}) أقل من الحد الأدنى للسحب (${min_amount:.2f}).\n"
                             f"الرجاء إدخال مبلغ صحيح:", parse_mode="HTML")
            return

        if current_balance < amount:
            bot.send_message(chat_id,
                             f"{balance_type_text} (${current_balance:.2f}) غير كافٍ لسحب هذا المبلغ (${amount:.2f}).\n"
                             f"يرجى إدخال مبلغ أقل.", parse_mode="HTML")
            return

        user_states[chat_id] = {
            "state": "waiting_payment_method_info",
            "amount": amount,
            "withdrawal_type": "referral",
            "message_id": original_message_id
        }
        bot.send_message(chat_id, "الرجاء إدخال معلومات طريقة الدفع (مثال: 'USDT TRC20: ABCXYZ123' أو 'رقم فودافون كاش: 01xxxxxxxxx'):", parse_mode="HTML")
    except Exception as e:
        print(f"خطأ في handle_withdrawal_amount_input: {e}\n{traceback.format_exc()}")
        bot.send_message(message.chat.id, "حدث خطأ أثناء معالجة السحب. يرجى المحاولة مرة أخرى.")
        if message.chat.id in user_states:
            del user_states[message.chat.id]


@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get("state") == "waiting_payment_method_info")
def handle_payment_method_info_input(message):
    try:
        chat_id = message.chat.id
        telegram_id = message.from_user.id

        if user_states.get(chat_id, {}).get("state") != "waiting_payment_method_info":
            bot.send_message(chat_id, "يبدو أن جلستك قد انتهت أو حدث خطأ. يرجى البدء من جديد باستخدام /start.", parse_mode="HTML")
            if chat_id in user_states:
                del user_states[chat_id]
            return

        state_info = user_states[chat_id]
        amount = state_info["amount"]
        withdrawal_type = state_info.get("withdrawal_type", "referral")
        payment_method_info = message.text.strip()
        original_message_id = state_info["message_id"]

        s = Session()
        user = s.query(User).filter_by(telegram_id=telegram_id).first()

        if not user:
            bot.send_message(chat_id, "حدث خطأ. يرجى المحاولة مرة أخرى أو التواصل مع الدعم.", parse_mode="HTML")
            s.close()
            del user_states[chat_id]
            return

        try:
            if withdrawal_type == "referral":
                user.referral_balance -= amount
                balance_after_withdrawal = user.referral_balance
                balance_type_text = "رصيد الإحالة الجديد"
            else:
                user.balance -= amount
                balance_after_withdrawal = user.balance
                balance_type_text = "رصيدك الجديد"

            new_withdrawal = Withdrawal(
                user_id=telegram_id,
                amount=amount,
                payment_method_info=payment_method_info,
                status="Pending",
                requested_at=datetime.now(),
                withdrawal_type=withdrawal_type
            )
            s.add(new_withdrawal)
            s.commit()

            confirmation_text = (
                f"✅ <b>تم استلام طلب السحب الخاص بك بنجاح!</b>\n\n"
                f"💲 <b>المبلغ:</b> ${amount:.2f}\n"
                f"💳 <b>طريقة الدفع:</b> {payment_method_info}\n"
                f"💰 <b>{balance_type_text}:</b> ${balance_after_withdrawal:.2f}\n\n"
                f"سيتم مراجعة طلبك من قبل المشرفين قريبًا. سيتم إشعارك عند معالجة السحب."
            )
            edit_message_text_and_markup(chat_id, original_message_id, confirmation_text, reply_markup=create_back_to_main_menu_inline_keyboard(), parse_mode="HTML")
            delete_message(chat_id, message.message_id)

            for admin_id in ADMIN_IDS:
                admin_notification_text = (
                    f"🔔 <b>طلب سحب جديد!</b>\n"
                    f"👤 <b>المستخدم:</b> {user.full_name or user.username} (ID: <code>{user.telegram_id}</code>)\n"
                    f"💲 <b>المبلغ:</b> ${amount:.2f}\n"
                    f"💳 <b>معلومات الدفع:</b> {payment_method_info}\n"
                    f"🆔 <b>معرف السحب:</b> <code>{new_withdrawal.id}</code>"
                )
                from utils import send_message_to_user
                send_message_to_user(admin_id, admin_notification_text, parse_mode="HTML")

        except Exception as e:
            s.rollback()
            bot.send_message(chat_id, f"حدث خطأ أثناء معالجة طلبك: {e}\nالرجاء المحاولة مرة أخرى أو التواصل مع الدعم.", parse_mode="HTML")
            print(f"خطأ في معالجة طلب السحب: {e}")
        finally:
            s.close()
            if chat_id in user_states:
                del user_states[chat_id]
    except Exception as e:
        print(f"خطأ في handle_payment_method_info_input: {e}\n{traceback.format_exc()}")
        bot.send_message(message.chat.id, "حدث خطأ أثناء معالجة السحب. يرجى المحاولة مرة أخرى.")
        if message.chat.id in user_states:
            del user_states[message.chat.id]

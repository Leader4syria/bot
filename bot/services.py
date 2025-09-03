import traceback
from telebot import types
from . import bot, user_states
from database import Session, Category, Service, Order, User
from utils import create_categories_keyboard, create_services_keyboard, edit_message_text_and_markup, delete_message, create_back_to_main_menu_inline_keyboard, send_message_to_user
from sqlalchemy.orm import joinedload
from receipt_generator import send_order_receipt
from config import ADMIN_IDS

@bot.callback_query_handler(func=lambda call: call.data == "show_services_menu")
def show_services_menu(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    s = Session()
    main_categories = s.query(Category).filter_by(parent_id=None).all()
    s.close()

    if not main_categories:
        edit_message_text_and_markup(chat_id, message_id, "لا توجد خدمات متاحة حاليًا. يرجى المحاولة لاحقًا.", reply_markup=create_back_to_main_menu_inline_keyboard(), parse_mode="HTML")
        bot.answer_callback_query(call.id, "لا توجد خدمات.")
        return

    keyboard = create_categories_keyboard(main_categories, back_button_data="main_menu")
    edit_message_text_and_markup(chat_id, message_id, "<b>اخـــــتـــر مــن الـــــقــــائــــمــــــة القــســم :</b>", reply_markup=keyboard, parse_mode="HTML")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('cat_'))
def callback_category_selection(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    category_id = int(call.data.split('_')[1])
    s = Session()
    selected_category = s.query(Category).get(category_id)

    if not selected_category:
        bot.answer_callback_query(call.id, "التصنيف غير موجود.", show_alert=True)
        s.close()
        return

    subcategories = s.query(Category).filter_by(parent_id=category_id).all()
    services_in_category = s.query(Service).filter_by(category_id=category_id, is_available=True).all()
    s.close()

    back_button_data = "main_menu"
    if selected_category.parent_id:
        back_button_data = f"cat_{selected_category.parent_id}"

    if subcategories:
        keyboard = create_categories_keyboard(subcategories, back_button_data=back_button_data)
        edit_message_text_and_markup(chat_id, message_id,
                                     f"انت داخل فئة<b><u>({selected_category.name})</u></b>:",
                                     reply_markup=keyboard, parse_mode="HTML")
    elif services_in_category:
        keyboard = create_services_keyboard(services_in_category, category_id, back_button_data=back_button_data)
        edit_message_text_and_markup(chat_id, message_id,
                                     f"<b>اخــــتـــر مـــن الــــــقــــائــــــمـــــة القسم :</b>",
                                     reply_markup=keyboard, parse_mode="HTML")
    else:
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=back_button_data))
        edit_message_text_and_markup(chat_id, message_id,
                                     f"لا توجد خدمات أو تصنيفات فرعية متاحة في '<b>{selected_category.name}</b>' حاليًا.",
                                     reply_markup=keyboard, parse_mode="HTML")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('service_'))
def callback_service_selection(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    service_id = int(call.data.split('_')[1])

    s = Session()
    service = s.query(Service).get(service_id)
    s.close()

    if not service or not service.is_available:
        bot.answer_callback_query(call.id, "الخدمة غير متاحة حاليًا أو غير موجودة.", show_alert=True)
        return

    user_states[chat_id] = {"state": "waiting_quantity", "service_id": service_id, "message_id": message_id}

    service_details_text = (
        f"<b>تفاصيل الخدمة:</b>\n"
        f"<blockquote>✨ <b>الاسم:</b> {service.name}</blockquote>\n"
        f"<blockquote>📝 <b>الوصف:</b> {service.description or 'لا يوجد وصف.'}</blockquote>\n"
        f"<blockquote>💲 <b>السعر:</b> ${service.base_price:.2f} لكل {service.base_quantity}</blockquote>\n"
        f"<blockquote>🔢 <b>الحد الأدنى للكمية:</b> {service.min_quantity}</blockquote>\n"
        f"<blockquote>🔢 <b>الحد الأقصى للكمية:</b> {service.max_quantity}</blockquote>\n\n"
        f" إدخل الكمية المطلوبة (مثال: {service.base_quantity}):"
    )

    back_button_data = f"cat_{service.category_id}"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 رجوع إلى التصنيف", callback_data=back_button_data))

    edit_message_text_and_markup(chat_id, message_id, service_details_text, reply_markup=markup, parse_mode="HTML")
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get("state") == "waiting_quantity")
def handle_quantity_input(message):
    try:
        chat_id = message.chat.id
        telegram_id = message.from_user.id

        if user_states.get(chat_id, {}).get("state") != "waiting_quantity":
            bot.send_message(
                chat_id,
                "يبدو أن جلستك قد انتهت أو حدث خطأ. يرجى البدء من جديد باستخدام /start.",
                parse_mode="HTML"
            )
            if chat_id in user_states:
                del user_states[chat_id]
            return

        state_info = user_states[chat_id]
        service_id = state_info["service_id"]
        original_message_id = state_info["message_id"]

        try:
            quantity = int(message.text)
            if quantity <= 0:
                raise ValueError
        except ValueError:
            bot.send_message(chat_id, "⚠️ كمية غير صالحة. الرجاء إدخال عدد صحيح موجب.", parse_mode="HTML")
            return

        s = Session()
        service = s.query(Service).options(joinedload(Service.category)).get(service_id)
        user = s.query(User).filter_by(telegram_id=telegram_id).first()

        if not service or not user:
            s.close()
            bot.send_message(chat_id, "❌ حدث خطأ. يرجى المحاولة مرة أخرى أو التواصل مع الدعم.", parse_mode="HTML")
            del user_states[chat_id]
            return

        category_name = service.category.name if service.category else "غير معروف"

        if quantity < service.min_quantity or quantity > service.max_quantity:
            s.close()
            bot.send_message(
                chat_id,
                f"⚠️ الكمية المطلوبة خارج النطاق المسموح به.\n"
                f"الحد الأدنى: {service.min_quantity}\n"
                f"الحد الأقصى: {service.max_quantity}\n"
                f"الرجاء إدخال كمية صحيحة:",
                parse_mode="HTML"
            )
            return

        total_price = (quantity / service.base_quantity) * service.base_price

        if user.balance < total_price:
            s.close()
            bot.send_message(
                chat_id,
                f"💸 رصيدك غير كافٍ لإتمام الطلب.\n"
                f"رصيدك الحالي: ${user.balance:.2f}\n"
                f"السعر الإجمالي للطلب: ${total_price:.2f}\n"
                f"🔋 يرجى شحن رصيدك أولاً.",
                parse_mode="HTML"
            )
            return

        user_states[chat_id] = {
            "state": "waiting_link_or_id",
            "service_id": service_id,
            "quantity": quantity,
            "total_price": total_price,
            "message_id": original_message_id
        }

        instructions = service.link_instructions if service.link_instructions else \
            "📌 الرجاء إرسال الرابط أو المعرف الخاص بالخدمة (مثال: رابط حساب، معرف منشور):"

        s.close()

        bot.send_message(chat_id, instructions, parse_mode="HTML")

    except Exception as e:
        print(f"خطأ في handle_quantity_input: {e}\n{traceback.format_exc()}")
        bot.send_message(message.chat.id, "⚠️ حدث خطأ أثناء معالجة الكمية. يرجى المحاولة مرة أخرى.")
        if message.chat.id in user_states:
            del user_states[message.chat.id]



@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get("state") == "waiting_link_or_id")
def handle_link_or_id_input(message):
    try:
        chat_id = message.chat.id
        telegram_id = message.from_user.id

        if user_states.get(chat_id, {}).get("state") != "waiting_link_or_id":
            bot.send_message(chat_id, "يبدو أن جلستك قد انتهت أو حدث خطأ. يرجى البدء من جديد باستخدام /start.", parse_mode="HTML")
            if chat_id in user_states:
                del user_states[chat_id]
            return

        state_info = user_states[chat_id]
        service_id = state_info["service_id"]
        quantity = state_info["quantity"]
        total_price = state_info["total_price"]
        link_or_id = message.text.strip()
        original_message_id = state_info["message_id"]

        s = Session()
        service = s.query(Service).get(service_id)
        user = s.query(User).filter_by(telegram_id=telegram_id).first()

        if not service or not user:
            bot.send_message(chat_id, "حدث خطأ. يرجى المحاولة مرة أخرى أو التواصل مع الدعم.", parse_mode="HTML")
            s.close()
            del user_states[chat_id]
            return

        try:
            user.balance -= total_price
            new_order = Order(
                user_id=telegram_id,
                service_id=service.id,
                quantity=quantity,
                link_or_id=link_or_id,
                total_price=total_price,
                status="Pending"
            )
            s.add(new_order)
            s.commit()

            confirmation_text = (
                f"✅ <b>تم تأكيد طلبك بنجاح!</b>\n\n"
                f"✨ <b>الخدمة:</b> {service.name}\n"
                f"🔢 <b>الكمية:</b> {quantity}\n"
                f"🔗 <b>الرابط/المعرف:</b> <code>{link_or_id}</code>\n"
                f"💲 <b>السعر الإجمالي:</b> ${total_price:.2f}\n"
                f"💰 <b>رصيدك الجديد:</b> ${user.balance:.2f}\n\n"
            )
            edit_message_text_and_markup(chat_id, original_message_id, confirmation_text, reply_markup=create_back_to_main_menu_inline_keyboard(), parse_mode="HTML")
            delete_message(chat_id, message.message_id)

            send_order_receipt(telegram_id, new_order.id)

            for admin_id in ADMIN_IDS:
                admin_notification_text = (
                    f"🔔 <b>طلب جديد!</b>\n"
                    f"👤 <b>المستخدم:</b> {user.full_name or user.username} (ID: <code>{user.telegram_id}</code>)\n"
                    f"✨ <b>الخدمة:</b> {service.name}\n"
                    f"🔢 <b>الكمية:</b> {quantity}\n"
                    f"🔗 <b>الرابط/المعرف:</b> <code>{link_or_id}</code>\n"
                    f"💲 <b>السعر الإجمالي:</b> ${total_price:.2f}\n"
                    f"🆔 <b>معرف الطلب:</b> <code>{new_order.id}</code>"
                )
                send_message_to_user(admin_id, admin_notification_text, parse_mode="HTML")

        except Exception as e:
            s.rollback()
            bot.send_message(chat_id, f"حدث خطأ أثناء معالجة طلبك: {e}\nالرجاء المحاولة مرة أخرى أو التواصل مع الدعم.", parse_mode="HTML")
            print(f"خطأ في معالجة الطلب: {e}")
        finally:
            s.close()
            if chat_id in user_states:
                del user_states[chat_id]
    except Exception as e:
        print(f"خطأ في handle_link_or_id_input: {e}\n{traceback.format_exc()}")
        bot.send_message(message.chat.id, "حدث خطأ أثناء معالجة الطلب. يرجى المحاولة مرة أخرى.")
        if message.chat.id in user_states:
            del user_states[message.chat.id]

from . import bot
from database import Session, User, Order
from utils import send_message_to_user, create_back_to_main_menu_inline_keyboard

def notify_user_order_status_update(order_id, new_status, user_telegram_id):
    s = Session()
    order = s.query(Order).get(order_id)
    user = s.query(User).filter_by(telegram_id=user_telegram_id).first()
    s.close()

    if order and user:
        status_message = ""
        if new_status == "Completed":
            status_message = "✅ <b>مكتملة!</b>"
        elif new_status == "Processing":
            status_message = "⏳ <b>قيد المعالجة.</b>"
        elif new_status == "Cancelled":
            status_message = "❌ <b>ملغاة.</b>"
        else:
            status_message = f"<b>{new_status}.</b>"

        notification_text = (
            f"🔔 <b>تحديث حالة طلبك!</b>\n\n"
            f"طلبك رقم <code>{order.id}</code> للخدمة '{order.service.name}' أصبح الآن: {status_message}\n"
            f"يمكنك التحقق من تفاصيل طلبك في قسم 'معلوماتي' أو التواصل مع الدعم إذا كان لديك أي استفسارات."
        )
        send_message_to_user(user_telegram_id, notification_text, reply_markup=create_back_to_main_menu_inline_keyboard(), parse_mode="HTML")
        print(f"تم إرسال إشعار تحديث حالة الطلب للمستخدم {user_telegram_id} للطلب {order_id} إلى {new_status}")
    else:
        print(f"لم يتم العثور على الطلب {order_id} أو المستخدم {user_telegram_id} لإرسال إشعار تحديث الحالة.")

def notify_user_withdrawal_status_update(withdrawal_id, new_status, user_telegram_id, amount, withdrawal_type):
    s = Session()
    user = s.query(User).filter_by(telegram_id=user_telegram_id).first()

    if user:
        status_message = ""
        notification_text = ""
        if new_status == "Approved":
            status_message = "✅ <b>تمت الموافقة!</b>"
            notification_text = (
                f"🔔 <b>تحديث حالة طلب السحب الخاص بك!</b>\n\n"
                f"طلب سحبك رقم <code>{withdrawal_id}</code> بمبلغ ${amount:.2f} {status_message}\n"
                f"سيتم التواصل معك قريباً لإتمام عملية السحب."
            )
        elif new_status == "Rejected":
            status_message = "❌ <b>تم الرفض.</b>"
            notification_text = (
                f"🔔 <b>تحديث حالة طلب السحب الخاص بك!</b>\n\n"
                f"طلب سحبك رقم <code>{withdrawal_id}</code> بمبلغ ${amount:.2f} {status_message}\n"
                f"يرجى التواصل مع الدعم لمزيد من التفاصيل."
            )
            if user:
                if withdrawal_type == "referral":
                    user.referral_balance += amount
                    notification_text += f"\nتمت إعادة ${amount:.2f} إلى رصيد الإحالة الخاص بك. رصيدك الحالي: ${user.referral_balance:.2f}"
                else:
                    user.balance += amount
                    notification_text += f"\nتمت إعادة ${amount:.2f} إلى رصيدك الأساسي. رصيدك الحالي: ${user.balance:.2f}"
                s.commit()
        else:
            status_message = f"<b>{new_status}.</b>"
            notification_text = (
                f"🔔 <b>تحديث حالة طلب السحب الخاص بك!</b>\n\n"
                f"طلب سحبك رقم <code>{withdrawal_id}</code> بمبلغ ${amount:.2f} أصبح الآن: {status_message}"
            )

        send_message_to_user(user_telegram_id, notification_text, reply_markup=create_back_to_main_menu_inline_keyboard(), parse_mode="HTML")
        print(f"تم إرسال إشعار تحديث حالة السحب للمستخدم {user_telegram_id} للسحب {withdrawal_id} إلى {new_status}")
    else:
        print(f"لم يتم العثور على المستخدم {user_telegram_id} لإرسال إشعار تحديث حالة السحب.")
    s.close()

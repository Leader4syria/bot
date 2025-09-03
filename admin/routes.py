from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, login_required, logout_user, current_user
from . import admin_bp, admin_required
from database import Session, User, Order, Payment, Withdrawal, Service
from sqlalchemy.orm import joinedload
from sqlalchemy import func
import traceback
from bot.start import send_message_to_user

from .auth import login_manager, AdminUser


@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    from config import ADMIN_IDS
    if current_user.is_authenticated and int(current_user.get_id()) in ADMIN_IDS:
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        return redirect(url_for('admin.admin_dashboard'))

    if request.method == 'POST':
        telegram_id_str = request.form.get('telegram_id')

        if not telegram_id_str:
            flash('الرجاء إدخال معرف تليجرام.', 'error')
            return render_template('login.html')

        try:
            telegram_id = int(telegram_id_str)
        except ValueError:
            flash('معرف تليجرام غير صالح.', 'error')
            return render_template('login.html')

        s = Session()
        user = s.query(User).filter_by(telegram_id=telegram_id, is_admin=True).first()
        s.close()

        if user and telegram_id in ADMIN_IDS:
            login_user(AdminUser(user.telegram_id))
            flash('تم تسجيل الدخول بنجاح!', 'success')

            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('admin.admin_dashboard'))
        else:
            flash('معرف تليجرام غير صحيح أو ليس لديك صلاحيات المشرف.', 'error')

    next_page = request.args.get('next')
    return render_template('login.html', next=next_page)

@admin_bp.route('/logout')
@login_required
def admin_logout():
    logout_user()
    flash('تم تسجيل الخروج بنجاح.', 'info')
    return redirect(url_for('admin.admin_login'))

@admin_bp.route('/')
@admin_required
def admin_dashboard():
    try:
        s = Session()
        total_users = s.query(User).count()
        total_services = s.query(Service).count()
        total_orders = s.query(Order).count()
        total_pending_orders = s.query(Order).filter_by(status="Pending").count()
        total_completed_orders = s.query(Order).filter_by(status="Completed").count()
        total_balance_sum = s.query(User).with_entities(func.sum(User.balance)).scalar() or 0.0
        total_referral_balance_sum = s.query(User).with_entities(func.sum(User.referral_balance)).scalar() or 0.0
        total_pending_withdrawals = s.query(Withdrawal).filter_by(status="Pending").count()

        orders = s.query(Order).options(joinedload(Order.user), joinedload(Order.service)).order_by(Order.ordered_at.desc()).limit(5).all()
        payments = s.query(Payment).options(joinedload(Payment.user)).order_by(Payment.paid_at.desc()).limit(5).all()

        s.close()

        return render_template('dashboard.html',
                               total_users=total_users,
                               total_services=total_services,
                               total_orders=total_orders,
                               total_pending_orders=total_pending_orders,
                               total_completed_orders=total_completed_orders,
                               total_balance_sum=total_balance_sum,
                               total_referral_balance_sum=total_referral_balance_sum,
                               total_pending_withdrawals=total_pending_withdrawals,
                               orders=orders,
                               payments=payments)
    except Exception as e:
        print(f"خطأ في admin_dashboard: {e}\n{traceback.format_exc()}")
        flash("حدث خطأ أثناء تحميل لوحة التحكم.", "error")
        return redirect(url_for('admin.admin_login'))

@admin_bp.route('/send_to_user', methods=['GET', 'POST'])
@admin_required
def admin_send_to_user():
    from utils import send_message_to_user
    try:
        if request.method == 'POST':
            telegram_id = request.form.get('telegram_id')
            message = request.form.get('message')
            message_type = request.form.get('message_type')

            if not all([telegram_id, message]):
                flash('الرجاء إدخال معرف التليجرام ونص الرسالة', 'error')
                return redirect(url_for('admin.admin_send_to_user'))

            try:
                telegram_id = int(telegram_id)
            except ValueError:
                flash('معرف التليجرام غير صالح', 'error')
                return redirect(url_for('admin.admin_send_to_user'))

            s = Session()
            user = s.query(User).filter_by(telegram_id=telegram_id).first()
            s.close()

            if not user:
                flash('المستخدم غير موجود', 'error')
                return redirect(url_for('admin.admin_send_to_user'))

            success = send_message_to_user(
                telegram_id,
                message,
                parse_mode="HTML" if message_type == "html" else None
            )

            if success:
                flash(f'تم إرسال الرسالة بنجاح إلى المستخدم {user.full_name or user.username}', 'success')
            else:
                flash('فشل إرسال الرسالة. قد يكون المستخدم حظر البوت أو لم يبدأ محادثة معه.', 'error')

            return redirect(url_for('admin.admin_send_to_user'))

        return render_template('send_to_user.html', broadcast_mode=False)
    except Exception as e:
        print(f"خطأ في admin_send_to_user: {e}\n{traceback.format_exc()}")
        flash("حدث خطأ غير متوقع أثناء إرسال الرسالة.", "error")
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/broadcast', methods=['GET', 'POST'])
@admin_required
def admin_broadcast():
    from utils import send_message_to_user
    try:
        if request.method == 'POST':
            message = request.form.get('message')
            message_type = request.form.get('message_type')

            if not message:
                flash('الرجاء إدخال نص الرسالة', 'error')
                return redirect(url_for('admin.admin_broadcast'))

            s = Session()
            users = s.query(User).all()
            s.close()

            sent_count = 0
            for user in users:
                success = send_message_to_user(
                    user.telegram_id,
                    message,
                    parse_mode="HTML" if message_type == "html" else None
                )
                if success:
                    sent_count += 1

            flash(f'تم إرسال الرسالة بنجاح إلى {sent_count} من المستخدمين.', 'success')
            return redirect(url_for('admin.admin_broadcast'))

        return render_template('broadcast.html', broadcast_mode=True)
    except Exception as e:
        print(f"خطأ في admin_broadcast: {e}\n{traceback.format_exc()}")
        flash("حدث خطأ غير متوقع أثناء بث الرسالة.", "error")
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.errorhandler(401)
def unauthorized(error):
    flash("غير مصرح لك بالوصول إلى هذه الصفحة. يرجى تسجيل الدخول.", "error")
    return redirect(url_for('admin.admin_login'))

@admin_bp.errorhandler(404)
def page_not_found(error):
    return "<h1>404 Page Not Found</h1>", 404

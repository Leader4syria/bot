from flask import render_template, request, redirect, url_for, flash
from . import admin_bp, admin_required
from database import Session, Payment
from sqlalchemy.orm import joinedload
import traceback
from bot.start import send_message_to_user

@admin_bp.route('/payments')
@admin_required
def admin_payments():
    try:
        s = Session()
        payments = s.query(Payment).options(joinedload(Payment.user)).order_by(Payment.paid_at.desc()).all()
        s.close()
        return render_template('payments.html', payments=payments)
    except Exception as e:
        print(f"خطأ في admin_payments: {e}\n{traceback.format_exc()}")
        flash("حدث خطأ غير متوقع أثناء تحميل صفحة المدفوعات.", "error")
        return redirect(url_for('admin.admin_dashboard'))

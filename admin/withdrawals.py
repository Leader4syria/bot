from flask import render_template, request, redirect, url_for, flash
from . import admin_bp, admin_required
from database import Session, Withdrawal
from sqlalchemy.orm import joinedload
from bot.notifications import notify_user_withdrawal_status_update
from bot import bot
from bot.start import send_message_to_user
import traceback

@admin_bp.route('/withdrawals')
@admin_required
def admin_withdrawals():
    try:
        s = Session()
        withdrawals = s.query(Withdrawal).options(joinedload(Withdrawal.user)).order_by(Withdrawal.requested_at.desc()).all()
        s.close()
        return render_template('withdrawals.html', withdrawals=withdrawals)
    except Exception as e:
        print(f"خطأ في admin_withdrawals: {e}\n{traceback.format_exc()}")
        flash("حدث خطأ غير متوقع أثناء تحميل صفحة طلبات السحب.", "error")
        return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/withdrawals/update_status/<int:withdrawal_id>', methods=['POST'])
@admin_required
def admin_update_withdrawal_status(withdrawal_id):
    try:
        new_status = request.form.get('new_status')
        valid_statuses = ['Pending', 'Completed', 'Canceled']

        if new_status not in valid_statuses:
            flash('حالة غير صالحة.', 'error')
            return redirect(url_for('admin.admin_withdrawals'))

        s = Session()
        withdrawal = s.query(Withdrawal).get(withdrawal_id)

        if not withdrawal:
            flash('طلب السحب غير موجود.', 'error')
            s.close()
            return redirect(url_for('admin.admin_withdrawals'))

        try:
            withdrawal.status = new_status
            s.commit()

            notify_user_withdrawal_status_update(bot, withdrawal.user, new_status)

            flash(f'تم تحديث حالة طلب السحب #{withdrawal.id} إلى {new_status} بنجاح.', 'success')

        except Exception as e:
            s.rollback()
            flash(f'حدث خطأ أثناء تحديث حالة السحب: {e}', 'error')
        finally:
            s.close()
        return redirect(url_for('admin.admin_withdrawals'))
    except Exception as e:
        print(f"خطأ في admin_update_withdrawal_status: {e}\n{traceback.format_exc()}")
        flash("حدث خطأ غير متوقع أثناء تحديث حالة طلب السحب.", "error")
        return redirect(url_for('admin.admin_withdrawals'))

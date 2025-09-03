from flask import render_template, request, redirect, url_for, flash, jsonify
from . import admin_bp, admin_required
from database import Session, User
from sqlalchemy import or_, String
import traceback
from bot.start import send_message_to_user

@admin_bp.route('/users')
@admin_required
def admin_users():
    try:
        search_query = request.args.get('search', '').strip()
        s = Session()

        if search_query:
            users = s.query(User).filter(
                or_(
                    User.telegram_id.cast(String).ilike(f'%{search_query}%'),
                    User.username.ilike(f'%{search_query}%'),
                    User.full_name.ilike(f'%{search_query}%'),
                    User.referral_code.ilike(f'%{search_query}%')
                )
            ).all()
        else:
            users = s.query(User).all()

        s.close()
        return render_template('users.html', users=users)
    except Exception as e:
        print(f"خطأ في admin_users: {e}\n{traceback.format_exc()}")
        flash("حدث خطأ أثناء تحميل قائمة المستخدمين.", "error")
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/users/edit_balance/<int:user_id>', methods=['POST'])
@admin_required
def admin_edit_user_balance(user_id):
    from utils import send_message_to_user
    try:
        new_balance = request.form.get('new_balance')
        s = Session()
        user = s.query(User).filter_by(telegram_id=user_id).first()

        if not user:
            flash('المستخدم غير موجود.', 'error')
            s.close()
            return redirect(url_for('admin.admin_users'))

        try:
            new_balance = float(new_balance)
            user.balance = new_balance
            s.commit()
            flash(f'تم تحديث رصيد المستخدم {user.full_name or user.username} الأساسي إلى ${new_balance:.2f} بنجاح.', 'success')
            send_message_to_user(user.telegram_id, f"💰 تم إضافة رصيد إلى حسابك!\nرصيدك الجديد هو: ${user.balance:.2f}")
        except ValueError:
            flash('الرصيد المدخل غير صالح.', 'error')
        except Exception as e:
            s.rollback()
            flash(f'حدث خطأ أثناء تحديث الرصيد: {e}', 'error')
        finally:
            s.close()
        return redirect(url_for('admin.admin_users'))
    except Exception as e:
        print(f"خطأ في admin_edit_user_balance: {e}\n{traceback.format_exc()}")
        flash("حدث خطأ غير متوقع أثناء تعديل رصيد المستخدم.", "error")
        return redirect(url_for('admin.admin_users'))


@admin_bp.route('/users/edit_referral_balance/<int:user_id>', methods=['POST'])
@admin_required
def admin_edit_user_referral_balance(user_id):
    from utils import send_message_to_user
    try:
        new_referral_balance = request.form.get('new_referral_balance')
        s = Session()
        user = s.query(User).filter_by(telegram_id=user_id).first()

        if not user:
            flash('المستخدم غير موجود.', 'error')
            s.close()
            return redirect(url_for('admin.admin_users'))

        try:
            new_referral_balance = float(new_referral_balance)
            user.referral_balance = new_referral_balance
            s.commit()
            flash(f'تم تحديث رصيد إحالة المستخدم {user.full_name or user.username} إلى ${new_referral_balance:.2f} بنجاح.', 'success')
            send_message_to_user(user.telegram_id, f"💸 <b>تم تحديث رصيد الإحالة الخاص بك!</b>\nرصيد الإحالة الجديد هو: ${user.referral_balance:.2f}", parse_mode="HTML")
        except ValueError:
            flash('الرصيد المدخل غير صالح.', 'error')
        except Exception as e:
            s.rollback()
            flash(f'حدث خطأ أثناء تحديث رصيد الإحالة: {e}', 'error')
        finally:
            s.close()
        return redirect(url_for('admin.admin_users'))
    except Exception as e:
        print(f"خطأ في admin_edit_user_referral_balance: {e}\n{traceback.format_exc()}")
        flash("حدث خطأ غير متوقع أثناء تعديل رصيد الإحالة.", "error")
        return redirect(url_for('admin.admin_users'))

@admin_bp.route("/api/users", methods=["GET"])
def get_users():
    s = Session()
    users = s.query(User).all()
    data = [
        {
            "id": u.id,
            "telegram_id": u.telegram_id,
            "username": u.username,
            "full_name": u.full_name,
            "balance": u.balance,
            "referral_balance": u.referral_balance
        } for u in users
    ]
    s.close()
    return jsonify(data)

@admin_bp.route('/api/admin/users/<int:user_id>/balance', methods=['POST'])
def api_admin_edit_user_balance(user_id):
    from . import api_key_required
    from utils import send_message_to_user
    try:
        data = request.get_json()
        if not data or 'new_balance' not in data:
            return jsonify({'success': False, 'message': 'الرصيد الجديد مطلوب'}), 400

        new_balance = data['new_balance']

        s = Session()
        user = s.query(User).filter_by(id=user_id).first()

        if not user:
            s.close()
            return jsonify({'success': False, 'message': 'المستخدم غير موجود'}), 404

        try:
            new_balance = float(new_balance)
            user.balance = new_balance
            s.commit()

            send_message_to_user(user.telegram_id, f"💰 تم إضافة رصيد إلى حسابك!\nرصيدك الجديد هو: ${user.balance:.2f}")

            s.close()
            return jsonify({
                'success': True,
                'message': f'تم تحديث الرصيد إلى ${new_balance:.2f}',
                'new_balance': user.balance
            })

        except ValueError:
            s.close()
            return jsonify({'success': False, 'message': 'الرصيد المدخل غير صالح'}), 400

    except Exception as e:
        if 's' in locals():
            s.close()
        return jsonify({'success': False, 'message': f'حدث خطأ: {str(e)}'}), 500

@admin_bp.route('/api/admin/users/<int:user_id>/referral_balance', methods=['POST'])
def api_admin_edit_user_referral_balance(user_id):
    from . import api_key_required
    from utils import send_message_to_user
    try:
        data = request.get_json()
        if not data or 'new_referral_balance' not in data:
            return jsonify({'success': False, 'message': 'رصيد الإحالة الجديد مطلوب'}), 400

        new_referral_balance = data['new_referral_balance']

        s = Session()
        user = s.query(User).filter_by(id=user_id).first()

        if not user:
            s.close()
            return jsonify({'success': False, 'message': 'المستخدم غير موجود'}), 404

        try:
            new_referral_balance = float(new_referral_balance)
            user.referral_balance = new_referral_balance
            s.commit()

            send_message_to_user(user.telegram_id, f"💸 تم تحديث رصيد الإحالة الخاص بك!\nرصيد الإحالة الجديد هو: ${user.referral_balance:.2f}")

            s.close()
            return jsonify({
                'success': True,
                'message': f'تم تحديث رصيد الإحالة إلى ${new_referral_balance:.2f}',
                'new_referral_balance': user.referral_balance
            })

        except ValueError:
            s.close()
            return jsonify({'success': False, 'message': 'رصيد الإحالة المدخل غير صالح'}), 400

    except Exception as e:
        if 's' in locals():
            s.close()
        return jsonify({'success': False, 'message': f'حدث خطأ: {str(e)}'}), 500

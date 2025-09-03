from flask import render_template, request, redirect, url_for, flash, jsonify
from . import admin_bp, admin_required
from bot.start import send_message_to_user
from database import Session, Order
from sqlalchemy.orm import joinedload
import traceback

@admin_bp.route('/orders')
@admin_required
def admin_orders():
    try:
        s = Session()
        orders = s.query(Order).options(joinedload(Order.user), joinedload(Order.service)).order_by(Order.ordered_at.desc()).all()
        s.close()
        return render_template('orders.html', orders=orders)
    except Exception as e:
        print(f"خطأ في admin_orders: {e}\n{traceback.format_exc()}")
        flash("حدث خطأ غير متوقع أثناء تحميل صفحة الطلبات.", "error")
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/orders/update_status/<int:order_id>', methods=['POST'])
@admin_required
def admin_update_order_status(order_id):
    from utils import send_message_to_user
    try:
        new_status = request.form.get('new_status')
        valid_statuses = ['Pending', 'Processing', 'Completed', 'Canceled']
        if new_status not in valid_statuses:
            flash('حالة غير صالحة.', 'error')
            return redirect(url_for('admin.admin_orders'))

        s = Session()
        order = s.query(Order).get(order_id)

        if not order:
            flash('الطلب غير موجود.', 'error')
            s.close()
            return redirect(url_for('admin.admin_orders'))

        try:
            order.status = new_status
            s.commit()

            service_name = order.service.name if order.service else "خدمة غير معروفة"
            if new_status == "Completed":
                message = f"✅ تم إكمال طلبك بنجاح!\nالطلب رقم #{order.id} للخدمة '{service_name}' تم إكماله. 🎉"
            elif new_status == "Canceled":
                message = f"❌ تم إلغاء طلبك!\nالطلب رقم #{order.id} للخدمة '{service_name}' تم إلغاؤه."
            else:
                message = f"🔔 تحديث حالة طلبك!\nالطلب رقم #{order.id} للخدمة '{service_name}' تم تحديث حالته إلى: {new_status}"

            send_message_to_user(order.user_id, message)

            flash(f'تم تحديث حالة الطلب #{order.id} إلى {new_status} بنجاح.', 'success')

        except Exception as e:
            s.rollback()
            flash(f'حدث خطأ أثناء تحديث حالة الطلب: {e}', 'error')
        finally:
            s.close()
        return redirect(url_for('admin.admin_orders'))
    except Exception as e:
        print(f"خطأ في admin_update_order_status: {e}\n{traceback.format_exc()}")
        flash("حدث خطأ غير متوقع أثناء تحديث حالة الطلب.", "error")
        return redirect(url_for('admin.admin_orders'))

@admin_bp.route("/api/orders", methods=["GET"])
def get_orders():
    try:
        s = Session()
        orders = s.query(Order).all()
        data = []
        for o in orders:
            data.append({
                "id": o.id,
                "user_id": o.user_id,
                "service_id": o.service_id,
                "quantity": o.quantity,
                "link_or_id": o.link_or_id,
                "total_price": o.total_price,
                "status": o.status,
                "ordered_at": o.ordered_at.strftime("%Y-%m-%d %H:%M:%S")
            })
        s.close()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/api/admin/orders/<int:order_id>/status', methods=['POST'])
def api_admin_update_order_status(order_id):
    from . import api_key_required
    from utils import send_message_to_user
    try:
        data = request.get_json()
        if not data or 'new_status' not in data:
            return jsonify({'success': False, 'message': 'الحالة الجديدة مطلوبة'}), 400

        new_status = data['new_status']
        valid_statuses = ['Pending', 'Processing', 'Completed', 'Canceled']

        if new_status not in valid_statuses:
            return jsonify({'success': False, 'message': 'حالة غير صالحة'}), 400

        s = Session()
        order = s.query(Order).get(order_id)

        if not order:
            s.close()
            return jsonify({'success': False, 'message': 'الطلب غير موجود'}), 404

        try:
            order.status = new_status
            s.commit()

            service_name = order.service.name if order.service else "خدمة غير معروفة"
            if new_status == "Completed":
                message = f"✅ تم إكمال طلبك بنجاح!\nالطلب رقم #{order.id} للخدمة '{service_name}' تم إكماله. 🎉"
            elif new_status == "Canceled":
                message = f"❌ تم إلغاء طلبك!\nالطلب رقم #{order.id} للخدمة '{service_name}' تم إلغاؤه."
            else:
                message = f"🔔 تحديث حالة طلبك!\nالطلب رقم #{order.id} للخدمة '{service_name}' تم تحديث حالته إلى: {new_status}"

            send_message_to_user(order.user_id, message)

            s.close()
            return jsonify({
                'success': True,
                'message': f'تم تحديث حالة الطلب إلى {new_status}',
                'new_status': new_status
            })

        except Exception as e:
            s.rollback()
            s.close()
            return jsonify({'success': False, 'message': f'حدث خطأ أثناء التحديث: {str(e)}'}), 500

    except Exception as e:
        if 's' in locals():
            s.close()
        return jsonify({'success': False, 'message': f'حدث خطأ: {str(e)}'}), 500

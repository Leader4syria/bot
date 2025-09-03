from flask import render_template, request, redirect, url_for, flash, send_file
from . import admin_bp, admin_required
from database import Session, User, Order, Service
from bot.start import send_message_to_user
from sqlalchemy import func, or_, String
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta
import traceback

def export_to_excel(orders, time_period, user_id, specific_date):
    try:
        import pandas as pd
        from openpyxl import Workbook
        from openpyxl.utils import get_column_letter
        from io import BytesIO

        data = []
        for order in orders:
            data.append({
                'رقم الطلب': order.id,
                'المستخدم': f"{order.user.full_name or order.user.username} ({order.user.telegram_id})",
                'الخدمة': order.service.name,
                'الكمية': order.quantity,
                'السعر الإجمالي': order.total_price,
                'الحالة': order.status,
                'التاريخ': order.ordered_at.strftime("%Y-%m-%d %H:%M:%S")
            })

        df = pd.DataFrame(data)

        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='الطلبات', index=False)

            stats_data = {
                'الإحصائية': ['عدد الطلبات', 'إجمالي الإيرادات', 'متوسط قيمة الطلب'],
                'القيمة': [len(orders), sum(order.total_price for order in orders),
                          sum(order.total_price for order in orders) / len(orders) if orders else 0]
            }
            stats_df = pd.DataFrame(stats_data)
            stats_df.to_excel(writer, sheet_name='الإحصائيات', index=False)

        output.seek(0)

        filename = f"إحصائيات_{time_period}"
        if specific_date:
            filename += f"_{specific_date}"
        if user_id:
            filename += f"_user_{user_id}"
        filename += ".xlsx"

        return send_file(output, download_name=filename, as_attachment=True)

    except ImportError:
        flash('حزمة pandas مطلوبة للتصدير إلى Excel', 'error')
        return redirect(url_for('admin.comprehensive_stats'))

def export_to_pdf(orders, time_period, user_id, specific_date):
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        from io import BytesIO
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import arabic_reshaper
        from bidi.algorithm import get_display

        pdfmetrics.registerFont(TTFont('ArabicFont', 'arial.ttf'))

        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)

        title = f"تقرير الإحصائيات - {time_period}"
        if specific_date:
            title += f" - {specific_date}"

        def draw_arabic_text(canvas, text, x, y, font_size=12):
            reshaped_text = arabic_reshaper.reshape(text)
            bidi_text = get_display(reshaped_text)
            canvas.setFont('ArabicFont', font_size)
            canvas.drawString(x, y, bidi_text)

        draw_arabic_text(c, title, 100, 750, 16)

        y_position = 700
        for order in orders[:50]:
            order_text = f"الطلب #{order.id} - {order.service.name} - ${order.total_price}"
            draw_arabic_text(c, order_text, 100, y_position)
            y_position -= 20

            if y_position < 100:
                c.showPage()
                y_position = 750

        c.save()
        buffer.seek(0)

        filename = f"إحصائيات_{time_period}"
        if specific_date:
            filename += f"_{specific_date}"
        filename += ".pdf"

        return send_file(buffer, download_name=filename, as_attachment=True, mimetype='application/pdf')

    except ImportError:
        flash('حزمة reportlab مطلوبة للتصدير إلى PDF', 'error')
        return redirect(url_for('admin.comprehensive_stats'))

@admin_bp.route('/comprehensive_stats')
@admin_required
def comprehensive_stats():
    from sqlalchemy import literal
    try:
        time_period = request.args.get('time_period', 'all')
        user_id = request.args.get('user_id', '')
        specific_date = request.args.get('specific_date', '')

        s = Session()

        all_users = s.query(User).all()

        base_query = s.query(Order).join(User)

        base_query = base_query.filter(User.telegram_id != 7721705352)

        if user_id:
            base_query = base_query.filter(User.telegram_id == int(user_id))

        now = datetime.now()
        if time_period == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            base_query = base_query.filter(Order.ordered_at >= start_date)
        elif time_period == 'yesterday':
            start_date = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            base_query = base_query.filter(Order.ordered_at >= start_date, Order.ordered_at < end_date)
        elif time_period == 'week':
            start_date = now - timedelta(days=now.weekday())
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            base_query = base_query.filter(Order.ordered_at >= start_date)
        elif time_period == 'month':
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            base_query = base_query.filter(Order.ordered_at >= start_date)
        elif time_period == 'specific' and specific_date:
            try:
                specific_date_obj = datetime.strptime(specific_date, '%Y-%m-%d')
                next_day = specific_date_obj + timedelta(days=1)
                base_query = base_query.filter(
                    Order.ordered_at >= specific_date_obj,
                    Order.ordered_at < next_day
                )
            except ValueError:
                flash('تاريخ غير صالح', 'error')

        total_orders = base_query.count()
        total_revenue = base_query.with_entities(func.sum(Order.total_price)).scalar() or 0.0
        avg_order_value = total_revenue / total_orders if total_orders > 0 else 0

        highest_balance_user = s.query(User).filter(User.telegram_id != 7721705352).order_by(User.balance.desc()).first()
        highest_balance = highest_balance_user.balance if highest_balance_user else 0

        user_stats_query = s.query(
            User.telegram_id,
            User.username,
            User.full_name,
            User.balance,
            User.referral_balance,
            func.count(Order.id).label('order_count'),
            func.coalesce(func.sum(Order.total_price), 0).label('total_spent')
        ).filter(User.telegram_id != 7721705352).outerjoin(Order).group_by(User.id)

        if user_id:
            user_stats_query = user_stats_query.filter(User.telegram_id == int(user_id))

        user_stats = user_stats_query.all()

        service_stats = s.query(
            Service.name,
            func.count(Order.id).label('order_count'),
            func.coalesce(func.sum(Order.total_price), 0).label('total_revenue')
        ).join(Order).join(User).filter(User.telegram_id != 7721705352).group_by(Service.id).order_by(func.sum(Order.total_price).desc()).limit(10).all()

        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        orders_today = s.query(Order).join(User).filter(User.telegram_id != 7721705352, Order.ordered_at >= today_start).count()
        revenue_today = s.query(func.coalesce(func.sum(Order.total_price), 0)).join(User).filter(User.telegram_id != 7721705352, Order.ordered_at >= today_start).scalar()
        new_users_today = s.query(User).filter(User.registered_at >= today_start, User.telegram_id != 7721705352).count()
        avg_order_today = revenue_today / orders_today if orders_today > 0 else 0

        daily_stats = {
            'orders_today': orders_today,
            'revenue_today': revenue_today,
            'new_users_today': new_users_today,
            'avg_order_today': avg_order_today
        }

        orders_movement = s.query(
            Order.ordered_at.label('date'),
            Order.user_id,
            User.full_name.label('user_name'),
            literal('order').label('type'),
            (-Order.total_price).label('amount'),
            (User.balance + Order.total_price).label('balance_before'),
            User.balance.label('balance_after')
            ).join(User).filter(User.telegram_id != 7721705352).order_by(Order.ordered_at.desc()).limit(50).all()

        balance_movements = []
        for movement in orders_movement:
            balance_movements.append({
                'date': movement.date,
                'user_id': movement.user_id,
                'user_name': movement.user_name,
                'type': movement.type,
                'amount': movement.amount,
                'balance_before': movement.balance_before,
                'balance_after': movement.balance_after
            })

        week_start = now - timedelta(days=7)
        orders_last_7_days = s.query(Order).join(User).filter(User.telegram_id != 7721705352, Order.ordered_at >= week_start).count()
        revenue_last_7_days = s.query(func.coalesce(func.sum(Order.total_price), 0)).join(User).filter(User.telegram_id != 7721705352, Order.ordered_at >= week_start).scalar()
        new_users_last_7_days = s.query(User).filter(User.registered_at >= week_start, User.telegram_id != 7721705352).count()

        weekly_stats = {
            'orders_last_7_days': orders_last_7_days,
            'revenue_last_7_days': revenue_last_7_days,
            'new_users_last_7_days': new_users_last_7_days
        }

        month_start = now - timedelta(days=30)
        orders_last_30_days = s.query(Order).join(User).filter(User.telegram_id != 7721705352, Order.ordered_at >= month_start).count()
        revenue_last_30_days = s.query(func.coalesce(func.sum(Order.total_price), 0)).join(User).filter(User.telegram_id != 7721705352, Order.ordered_at >= month_start).scalar()

        monthly_stats = {
            'orders_last_30_days': orders_last_30_days,
            'revenue_last_30_days': revenue_last_30_days
        }

        s.close()

        return render_template('comprehensive_stats.html',
                               total_revenue=total_revenue,
                               total_orders=total_orders,
                               avg_order_value=avg_order_value,
                               highest_balance=highest_balance,
                               user_stats=user_stats,
                               service_stats=service_stats,
                               daily_stats=daily_stats,
                               balance_movements=balance_movements[:50],
                               weekly_stats=weekly_stats,
                               monthly_stats=monthly_stats,
                               all_users=all_users,
                               time_period=time_period,
                               user_id=user_id,
                               specific_date=specific_date)

    except Exception as e:
        print(f"خطأ في comprehensive_stats: {e}\n{traceback.format_exc()}")
        flash("حدث خطأ أثناء تحميل الإحصائيات الشاملة.", "error")
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/export_stats')
@admin_required
def export_stats():
    export_format = request.args.get('format', 'excel')
    time_period = request.args.get('time_period', 'all')
    user_id = request.args.get('user_id', '')
    specific_date = request.args.get('specific_date', '')

    try:
        s = Session()

        base_query = s.query(Order).join(User).filter(User.telegram_id != 7721705352)

        if user_id:
            base_query = base_query.filter(User.telegram_id == int(user_id))

        now = datetime.now()
        if time_period == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            base_query = base_query.filter(Order.ordered_at >= start_date)
        elif time_period == 'yesterday':
            start_date = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            base_query = base_query.filter(Order.ordered_at >= start_date, Order.ordered_at < end_date)
        elif time_period == 'week':
            start_date = now - timedelta(days=now.weekday())
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            base_query = base_query.filter(Order.ordered_at >= start_date)
        elif time_period == 'month':
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            base_query = base_query.filter(Order.ordered_at >= start_date)
        elif time_period == 'specific' and specific_date:
            try:
                specific_date_obj = datetime.strptime(specific_date, '%Y-%m-%d')
                next_day = specific_date_obj + timedelta(days=1)
                base_query = base_query.filter(
                    Order.ordered_at >= specific_date_obj,
                    Order.ordered_at < next_day
                )
            except ValueError:
                flash('تاريخ غير صالح', 'error')

        orders = base_query.options(
            joinedload(Order.user),
            joinedload(Order.service)
        ).all()

        s.close()

        if export_format == 'excel':
            return export_to_excel(orders, time_period, user_id, specific_date)
        elif export_format == 'pdf':
            return export_to_pdf(orders, time_period, user_id, specific_date)
        else:
            flash('صيغة التصدير غير مدعومة', 'error')
            return redirect(url_for('admin.comprehensive_stats'))

    except Exception as e:
        print(f"خطأ في export_stats: {e}")
        flash("حدث خطأ أثناء التصدير", "error")
        return redirect(url_for('admin.comprehensive_stats'))

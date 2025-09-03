from flask import render_template, request, redirect, url_for, flash
from . import admin_bp, admin_required
from database import Session, Service, Category
from sqlalchemy.orm import joinedload
import traceback
from flask_wtf.csrf import generate_csrf

@admin_bp.route('/services', methods=['GET'])
@admin_required
def admin_services():
    try:
        session = Session()
        services = session.query(Service).options(joinedload(Service.category)).all()
        categories = session.query(Category).all()
        session.close()
        return render_template('services.html', services=services, categories=categories, csrf_token=generate_csrf())
    except Exception as e:
        print(f"خطأ في admin_services: {e}\n{traceback.format_exc()}")
        flash("حدث خطأ غير متوقع أثناء تحميل صفحة الخدمات.", "error")
        return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/services/add', methods=['POST'])
@admin_required
def admin_add_service():
    try:
        name = request.form.get('name')
        description = request.form.get('description')
        base_price = request.form.get('base_price')
        base_quantity = request.form.get('base_quantity')
        min_quantity = request.form.get('min_quantity')
        max_quantity = request.form.get('max_quantity')
        link_instructions = request.form.get('link_instructions')
        category_id = request.form.get('category_id')
        is_available = request.form.get('is_available') == 'on'

        if not all([name, base_price, base_quantity, category_id]):
            flash('الرجاء ملء جميع الحقول المطلوبة (الاسم، السعر الأساسي، الكمية الأساسية، التصنيف).', 'error')
            return redirect(url_for('admin.admin_services'))

        s = Session()
        try:
            base_price = float(base_price)
            base_quantity = int(base_quantity)
            min_quantity = int(min_quantity) if min_quantity else 1
            max_quantity = int(max_quantity) if max_quantity else 100000
            category_id = int(category_id)
            new_service = Service(
                name=name,
                description=description,
                base_price=base_price,
                base_quantity=base_quantity,
                min_quantity=min_quantity,
                max_quantity=max_quantity,
                link_instructions=link_instructions,
                category_id=category_id,
                is_available=is_available
            )
            s.add(new_service)
            s.commit()
            flash(f'تم إضافة الخدمة "{name}" بنجاح.', 'success')
        except ValueError:
            flash('الرجاء إدخال قيم رقمية صحيحة للكمية والسعر.', 'error')
        except Exception as e:
            s.rollback()
            flash(f'حدث خطأ أثناء إضافة الخدمة: {e}', 'error')
        finally:
            s.close()
        return redirect(url_for('admin.admin_services'))
    except Exception as e:
        print(f"خطأ في admin_add_service: {e}\n{traceback.format_exc()}")
        flash("حدث خطأ غير متوقع أثناء إضافة الخدمة.", "error")
        return redirect(url_for('admin.admin_services'))


@admin_bp.route('/services/edit/<int:service_id>', methods=['POST'])
@admin_required
def admin_edit_service(service_id):
    try:
        name = request.form.get('name')
        description = request.form.get('description')
        base_price = request.form.get('base_price')
        base_quantity = request.form.get('base_quantity')
        min_quantity = request.form.get('min_quantity')
        max_quantity = request.form.get('max_quantity')
        link_instructions = request.form.get('link_instructions')
        category_id = request.form.get('category_id')
        is_available = request.form.get('is_available') == 'on'

        s = Session()
        service = s.query(Service).get(service_id)

        if not service:
            s.close()
            flash('الخدمة غير موجودة.', 'error')
            return redirect(url_for('admin.admin_services'))

        try:
            service.name = name
            service.description = description
            service.base_price = float(base_price)
            service.base_quantity = int(base_quantity)
            service.min_quantity = int(min_quantity) if min_quantity else 1
            service.max_quantity = int(max_quantity) if max_quantity else 100000
            service.link_instructions = link_instructions
            service.category_id = int(category_id)
            service.is_available = is_available
            s.commit()
            flash(f'تم تحديث الخدمة "{service.name}" بنجاح.', 'success')
        except ValueError:
            s.rollback()
            flash('الرجاء إدخال قيم رقمية صحيحة.', 'error')
        except Exception as e:
            s.rollback()
            flash(f'حدث خطأ أثناء تحديث الخدمة: {e}', 'error')
        finally:
            s.close()
        return redirect(url_for('admin.admin_services'))
    except Exception as e:
        print(f"خطأ في admin_edit_service: {e}\n{traceback.format_exc()}")
        flash("حدث خطأ غير متوقع أثناء تعديل الخدمة.", "error")
        return redirect(url_for('admin.admin_services'))


@admin_bp.route('/services/delete/<int:service_id>', methods=['POST'])
@admin_required
def admin_delete_service(service_id):
    try:
        s = Session()
        service = s.query(Service).get(service_id)
        if not service:
            s.close()
            flash('الخدمة غير موجودة.', 'error')
            return redirect(url_for('admin.admin_services'))

        try:
            s.delete(service)
            s.commit()
            flash(f'تم حذف الخدمة "{service.name}" بنجاح.', 'success')
        except Exception as e:
            s.rollback()
            flash(f'حدث خطأ أثناء حذف الخدمة: {e}', 'error')
        finally:
            s.close()
        return redirect(url_for('admin.admin_services'))
    except Exception as e:
        print(f"خطأ في admin_delete_service: {e}\n{traceback.format_exc()}")
        flash("حدث خطأ غير متوقع أثناء حذف الخدمة.", "error")
        return redirect(url_for('admin.admin_services'))
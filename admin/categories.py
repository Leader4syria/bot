from flask import render_template, request, redirect, url_for, flash
from . import admin_bp, admin_required
from database import Session, Category, Service
from sqlalchemy.orm import joinedload
from flask_wtf.csrf import generate_csrf
from bot.start import send_message_to_user
import traceback

@admin_bp.route('/categories')
@admin_required
def admin_categories():
    try:
        s = Session()
        categories = s.query(Category).options(joinedload(Category.parent)).all()
        all_categories = s.query(Category).all()
        s.close()
        return render_template('categories.html', categories=categories, all_categories=all_categories, csrf_token=generate_csrf())
    except Exception as e:
        print(f"خطأ في admin_categories: {e}\n{traceback.format_exc()}")
        flash("حدث خطأ أثناء تحميل قائمة التصنيفات.", "error")
        return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/categories/add', methods=['POST'])
@admin_required
def admin_add_category():
    try:
        name = request.form.get('name')
        parent_id = request.form.get('parent_id')

        if not name:
            flash('اسم التصنيف مطلوب.', 'error')
            return redirect(url_for('admin.admin_categories'))

        s = Session()
        existing_category = s.query(Category).filter_by(name=name).first()
        if existing_category:
            flash('تصنيف بهذا الاسم موجود بالفعل.', 'error')
            s.close()
            return redirect(url_for('admin.admin_categories'))

        try:
            if parent_id and parent_id != 'None':
                parent_id = int(parent_id)
                new_category = Category(name=name, parent_id=parent_id)
            else:
                new_category = Category(name=name, parent_id=None)
            s.add(new_category)
            s.commit()
            flash(f'تم إضافة التصنيف "{name}" بنجاح.', 'success')
        except Exception as e:
            s.rollback()
            flash(f'حدث خطأ أثناء إضافة التصنيف: {e}', 'error')
        finally:
            s.close()
        return redirect(url_for('admin.admin_categories'))
    except Exception as e:
        print(f"خطأ في admin_add_category: {e}\n{traceback.format_exc()}")
        flash("حدث خطأ غير متوقع أثناء إضافة التصنيف.", "error")
        return redirect(url_for('admin.admin_categories'))


@admin_bp.route('/categories/edit/<int:category_id>', methods=['POST'])
@admin_required
def admin_edit_category(category_id):
    name = request.form.get('name')
    parent_id = request.form.get('parent_id')

    s = Session()
    category = s.query(Category).get(category_id)

    if not category:
        flash('التصنيف غير موجود.', 'error')
        s.close()
        return redirect(url_for('admin.admin_categories'))

    if not name:
        flash('اسم التصنيف مطلوب.', 'error')
        s.close()
        return redirect(url_for('admin.admin_categories'))

    try:
        category.name = name
        if parent_id and parent_id != 'None':
            parent_id = int(parent_id)
            category.parent_id = parent_id
        else:
            category.parent_id = None
        s.commit()
        flash(f'تم تحديث التصنيف "{name}" بنجاح.', 'success')
    except Exception as e:
        s.rollback()
        flash(f'حدث خطأ أثناء تحديث التصنيف: {e}', 'error')
    finally:
        s.close()

    return redirect(url_for('admin.admin_categories'))


@admin_bp.route('/categories/delete/<int:category_id>', methods=['POST'])
@admin_required
def admin_delete_category(category_id):
    try:
        s = Session()
        category = s.query(Category).get(category_id)

        if not category:
            flash('التصنيف غير موجود.', 'error')
            s.close()
            return redirect(url_for('admin.admin_categories'))

        try:
            s.query(Service).filter_by(category_id=category_id).delete()
            s.delete(category)
            s.commit()
            flash(f'تم حذف التصنيف "{category.name}" وجميع الخدمات والتصنيفات الفرعية المرتبطة به بنجاح.', 'success')
        except Exception as e:
            s.rollback()
            flash(f'حدث خطأ أثناء حذف التصنيف: {e}', 'error')
        finally:
            s.close()
        return redirect(url_for('admin.admin_categories'))
    except Exception as e:
        print(f"خطأ في admin_delete_category: {e}\n{traceback.format_exc()}")
        flash("حدث خطأ غير متوقع أثناء حذف التصنيف.", "error")
        return redirect(url_for('admin.admin_categories'))

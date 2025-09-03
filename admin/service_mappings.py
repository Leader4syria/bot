from flask import render_template, request, redirect, url_for, flash
from . import admin_bp, admin_required
from database import Session, Service, ServiceProvider, ServiceMapping
from smm_providers import SMMProvider
from sqlalchemy.orm import joinedload
from bot.start import send_message_to_user
from flask_wtf.csrf import generate_csrf
import traceback

@admin_bp.route('/service_mappings')
@admin_required
def admin_service_mappings():
    try:
        s = Session()

        providers = s.query(ServiceProvider).all()
        services = s.query(Service).options(joinedload(Service.category)).all()

        service_mappings = s.query(ServiceMapping).options(
            joinedload(ServiceMapping.service).joinedload(Service.category),
            joinedload(ServiceMapping.provider)
        ).all()

        s.close()

        return render_template(
            'service_mappings.html',
            providers=providers,
            services=services,
            service_mappings=service_mappings,
            provider_services=None,
            csrf_token=generate_csrf()
        )

    except Exception as e:
        flash(f"حدث خطأ: {e}", "error")
        s = Session()
        providers = s.query(ServiceProvider).all()
        services = s.query(Service).options(joinedload(Service.category)).all()
        service_mappings = []
        s.close()

        return render_template(
            'service_mappings.html',
            providers=providers,
            services=services,
            service_mappings=service_mappings,
            provider_services=None,
            csrf_token=generate_csrf()
        )

@admin_bp.route('/add_provider', methods=['POST'])
@admin_required
def admin_add_provider():
    try:
        name = request.form.get('name')
        api_url = request.form.get('api_url')
        api_key = request.form.get('api_key')
        is_active = request.form.get('is_active') == 'on'

        s = Session()
        provider = ServiceProvider(
            name=name,
            api_url=api_url,
            api_key=api_key,
            is_active=is_active
        )
        s.add(provider)
        s.commit()
        s.close()

        flash("تم إضافة المزود بنجاح", "success")
        return redirect(url_for('admin.admin_service_mappings'))

    except Exception as e:
        flash(f"حدث خطأ: {e}", "error")
        return redirect(url_for('admin.admin_service_mappings'))

@admin_bp.route('/add_service_mapping', methods=['POST'])
@admin_required
def admin_add_service_mapping():
    try:
        service_id = request.form.get('service_id')
        provider_id = request.form.get('provider_id')
        provider_service_id = request.form.get('provider_service_id')
        min_quantity = request.form.get('min_quantity', 0)
        max_quantity = request.form.get('max_quantity', 1000000)

        s = Session()

        service = s.query(Service).get(service_id)

        if not service:
            flash("الخدمة غير موجودة", "error")
            s.close()
            return redirect(url_for('admin.admin_service_mappings'))

        provider = SMMProvider(provider_id)
        provider_services = provider.get_services()

        if 'error' in provider_services:
            flash(f"خطأ في جلب خدمات المزود: {provider_services['error']}", "error")
            s.close()
            return redirect(url_for('admin.admin_service_mappings'))

        provider_price = None
        for svc in provider_services:
            if str(svc.get('service')) == str(provider_service_id):
                provider_price = float(svc.get('rate', 0))
                break

        if provider_price is None or provider_price <= 0:
            flash("لم يتم العثور على سعر الخدمة لدى المزود أو السعر غير صالح", "error")
            s.close()
            return redirect(url_for('admin.admin_service_mappings'))

        price_multiplier = service.base_price / provider_price

        mapping = ServiceMapping(
            service_id=service_id,
            provider_id=provider_id,
            provider_service_id=provider_service_id,
            min_quantity=min_quantity,
            max_quantity=max_quantity,
            price_multiplier=price_multiplier
        )
        s.add(mapping)
        s.commit()
        s.close()

        flash("تم ربط الخدمة بنجاح", "success")
        return redirect(url_for('admin.admin_service_mappings'))

    except Exception as e:
        flash(f"حدث خطأ: {e}", "error")
        return redirect(url_for('admin.admin_service_mappings'))

@admin_bp.route('/fetch_provider_services', methods=['POST'])
@admin_required
def admin_fetch_provider_services():
    try:
        provider_id = request.form.get('provider_id')

        provider = SMMProvider(provider_id)
        services = provider.get_services()

        s = Session()
        providers = s.query(ServiceProvider).all()
        service_mappings = s.query(ServiceMapping).options(
            joinedload(ServiceMapping.service),
            joinedload(ServiceMapping.provider)
        ).all()
        s.close()

        if 'error' in services:
            flash(f"خطأ في جلب الخدمات: {services['error']}", "error")
            services = []

        return render_template('service_mappings.html',
                             providers=providers,
                             services=s.query(Service).all(),
                             service_mappings=service_mappings,
                             provider_services=services,
                             csrf_token=generate_csrf())

    except Exception as e:
        flash(f"حدث خطأ: {e}", "error")
        return redirect(url_for('admin.admin_service_mappings'))

@admin_bp.route('/delete_provider/<int:provider_id>', methods=['POST'])
@admin_required
def admin_delete_provider(provider_id):
    try:
        s = Session()
        provider = s.query(ServiceProvider).get(provider_id)
        if provider:
            s.delete(provider)
            s.commit()
            flash("تم حذف المزود بنجاح", "success")
        else:
            flash("المزود غير موجود", "error")
        s.close()
        return redirect(url_for('admin.admin_service_mappings'))

    except Exception as e:
        flash(f"حدث خطأ: {e}", "error")
        return redirect(url_for('admin.admin_service_mappings'))

@admin_bp.route('/delete_service_mapping/<int:mapping_id>', methods=['POST'])
@admin_required
def admin_delete_service_mapping(mapping_id):
    try:
        s = Session()
        mapping = s.query(ServiceMapping).get(mapping_id)
        if mapping:
            s.delete(mapping)
            s.commit()
            flash("تم حذف الربط بنجاح", "success")
        else:
            flash("الربط غير موجود", "error")
        s.close()
        return redirect(url_for('admin.admin_service_mappings'))

    except Exception as e:
        flash(f"حدث خطأ: {e}", "error")
        return redirect(url_for('admin.admin_service_mappings'))

@admin_bp.route('/add_service_from_provider', methods=['POST'])
@admin_required
def admin_add_service_from_provider():
    try:
        provider_service_id = request.form.get('provider_service_id')
        provider_id = request.form.get('provider_id')
        category_id = request.form.get('category_id')
        service_price = float(request.form.get('service_price'))
        min_quantity = int(request.form.get('min_quantity', 0))
        max_quantity = int(request.form.get('max_quantity', 1000000))

        s = Session()

        provider = s.query(ServiceProvider).get(provider_id)
        if not provider:
            flash("المزود غير موجود", "error")
            s.close()
            return redirect(url_for('admin.admin_service_mappings'))

        smm_provider = SMMProvider(provider_id)
        provider_services = smm_provider.get_services()

        if 'error' in provider_services:
            flash(f"خطأ في جلب الخدمات: {provider_services['error']}", "error")
            s.close()
            return redirect(url_for('admin.admin_service_mappings'))

        service_info = None
        for service in provider_services:
            if str(service.get('service')) == str(provider_service_id):
                service_info = service
                break

        if not service_info:
            flash("لم يتم العثور على الخدمة لدى المزود", "error")
            s.close()
            return redirect(url_for('admin.admin_service_mappings'))

        provider_min = int(service_info.get('min', 0))
        provider_max = int(service_info.get('max', 1000000))
        provider_price = float(service_info.get('rate', 0))

        if min_quantity < provider_min:
            min_quantity = provider_min
        if max_quantity > provider_max:
            max_quantity = provider_max

        price_multiplier = service_price / provider_price

        new_service = Service(
            name=service_info.get('name', 'خدمة بدون اسم'),
            description=service_info.get('name', ''),
            base_price=service_price,
            base_quantity=1000,
            min_quantity=min_quantity,
            max_quantity=max_quantity,
            category_id=category_id,
            is_available=True
        )

        s.add(new_service)
        s.flush()

        mapping = ServiceMapping(
            service_id=new_service.id,
            provider_id=provider_id,
            provider_service_id=provider_service_id,
            min_quantity=min_quantity,
            max_quantity=max_quantity,
            price_multiplier=price_multiplier
        )

        s.add(mapping)
        s.commit()

        flash("تم إضافة الخدمة وربطها بنجاح", "success")

    except Exception as e:
        s.rollback()
        flash(f"حدث خطأ: {e}", "error")
    finally:
        s.close()

    return redirect(url_for('admin.admin_service_mappings'))

@admin_bp.route('/update_service_mapping', methods=['POST'])
@admin_required
def admin_update_service_mapping():
    try:
        mapping_id = request.form.get('mapping_id')
        price_multiplier = 1.0
        min_quantity = int(request.form.get('min_quantity', 0))
        max_quantity = int(request.form.get('max_quantity', 1000000))

        s = Session()
        mapping = s.query(ServiceMapping).get(mapping_id)

        if not mapping:
            flash("الربط غير موجود", "error")
            s.close()
            return redirect(url_for('admin.admin_service_mappings'))

        mapping.price_multiplier = price_multiplier
        mapping.min_quantity = min_quantity
        mapping.max_quantity = max_quantity

        s.commit()
        flash("تم تحديث الربط بنجاح", "success")

    except Exception as e:
        s.rollback()
        flash(f"حدث خطأ: {e}", "error")
    finally:
        s.close()

    return redirect(url_for('admin.admin_service_mappings'))

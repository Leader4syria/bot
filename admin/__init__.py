from flask import Blueprint, flash, redirect, url_for, request, jsonify
from flask_login import current_user
from functools import wraps
from config import ADMIN_IDS, API_KEY
from database import Session, User

admin_bp = Blueprint('admin', __name__, url_prefix='/admin', template_folder='../templates')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or int(current_user.get_id()) not in ADMIN_IDS:
            flash('غير مصرح لك بالوصول إلى هذه الصفحة. يرجى تسجيل الدخول بحساب مشرف.', 'error')
            return redirect(url_for('admin.admin_login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def api_key_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        provided_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        if not provided_key or provided_key != API_KEY:
            return jsonify({'success': False, 'message': 'مفتاح API غير صالح أو مفقود'}), 401
        return f(*args, **kwargs)
    return decorated_function

from . import routes, users, services, categories, orders, stats, service_mappings, payment_methods, withdrawals, api_routes

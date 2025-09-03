from flask import Blueprint, jsonify, request
from . import api_key_required
from database import Session, User, Service, Order, Payment, Withdrawal
from sqlalchemy import func
from bot.notifications import broadcast_message_to_all_users

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/stats', methods=['GET'])
@api_key_required
def get_stats():
    """
    Returns bot statistics.
    """
    s = Session()
    try:
        total_users = s.query(User).count()
        total_services = s.query(Service).count()
        total_orders = s.query(Order).count()
        total_pending_orders = s.query(Order).filter(Order.status == 'Pending').count()
        total_completed_orders = s.query(Order).filter(Order.status == 'Completed').count()
        total_balance = s.query(func.sum(User.balance)).scalar() or 0.0
        total_referral_balance = s.query(func.sum(User.referral_balance)).scalar() or 0.0
        total_pending_withdrawals = s.query(Withdrawal).filter(Withdrawal.status == 'Pending').count()

        stats = {
            'total_users': total_users,
            'total_services': total_services,
            'total_orders': total_orders,
            'total_pending_orders': total_pending_orders,
            'total_completed_orders': total_completed_orders,
            'total_balance': f"{total_balance:.2f}",
            'total_referral_balance': f"{total_referral_balance:.2f}",
            'total_pending_withdrawals': total_pending_withdrawals,
        }
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({"message": f"An error occurred: {e}"}), 500
    finally:
        s.close()

@api_bp.route('/broadcast', methods=['POST'])
@api_key_required
def broadcast_message():
    """
    Broadcasts a message to all subscribed users.
    """
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({"message": "Message is required"}), 400

    message_text = data['message']
    parse_mode = data.get('parse_mode', None)

    try:
        sent_count = broadcast_message_to_all_users(message_text, parse_mode=parse_mode)
        return jsonify({"message": f"Message sent to {sent_count} users."}), 200
    except Exception as e:
        return jsonify({"message": f"An error occurred: {e}"}), 500

@api_bp.route('/users/<int:telegram_id>/balance', methods=['POST'])
@api_key_required
def update_user_balance(telegram_id):
    """
    Updates a user's balance.
    """
    data = request.get_json()
    if not data or 'amount' not in data or 'action' not in data:
        return jsonify({"message": "Amount and action are required"}), 400

    amount = data['amount']
    action = data['action']

    if action not in ['add', 'subtract']:
        return jsonify({"message": "Invalid action. Use 'add' or 'subtract'."}), 400

    s = Session()
    try:
        user = s.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return jsonify({"message": "User not found"}), 404

        if action == 'add':
            user.balance += amount
        else:
            if user.balance < amount:
                return jsonify({"message": "Insufficient balance"}), 400
            user.balance -= amount

        s.commit()
        return jsonify({
            "message": "Balance updated successfully",
            "new_balance": f"{user.balance:.2f}"
        }), 200
    except Exception as e:
        s.rollback()
        return jsonify({"message": f"An error occurred: {e}"}), 500
    finally:
        s.close()

@api_bp.route('/services/<int:service_id>', methods=['PUT'])
@api_key_required
def update_service(service_id):
    """
    Updates a service's details.
    """
    data = request.get_json()
    if not data:
        return jsonify({"message": "Data is required"}), 400

    s = Session()
    try:
        service = s.query(Service).get(service_id)
        if not service:
            return jsonify({"message": "Service not found"}), 404

        if 'name' in data:
            service.name = data['name']
        if 'base_price' in data:
            service.base_price = data['base_price']

        s.commit()
        return jsonify({"message": "Service updated successfully"}), 200
    except Exception as e:
        s.rollback()
        return jsonify({"message": f"An error occurred: {e}"}), 500
    finally:
        s.close()

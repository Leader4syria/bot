import threading
import time
from datetime import datetime
from io import BytesIO
from telebot import TeleBot
from database import init_db, Session, User, Category, Service, Order
from flask import Flask, jsonify, request
from pyngrok import ngrok, conf
import bot
import os
from admin.auth import login_manager
from admin import admin_bp
import config
from config import FLASK_PORT, ADMIN_IDS, BACKUP_GROUB, BOT_TOKEN, GROUP_ID, FLASK_SECRET_KEY
import hmac
import hashlib
import json
from sqlalchemy.orm import joinedload
from urllib.parse import parse_qsl

app = Flask(__name__, static_folder='web')
app.config['SECRET_KEY'] = FLASK_SECRET_KEY
app.register_blueprint(admin_bp)
login_manager.init_app(app)

backup_bot = TeleBot(BOT_TOKEN)

def send_backup_to_group():
    try:
        backup_data = BytesIO()
        with open('bot_data.db', 'rb') as f:
            backup_data.write(f.read())
        backup_data.seek(0)
        
        backup_bot.send_document(
            BACKUP_GROUB,
            backup_data,
            caption=f"نسخة احتياطية تلقائية - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            visible_file_name=f"bot_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        )
        print(f"تم إرسال النسخة الاحتياطية للكروب في {datetime.now()}")
    except Exception as e:
        print(f"خطأ في النسخ الاحتياطي التلقائي: {e}")

def backup_scheduler():
    while True:
        try:
            now = datetime.now()
            next_hour = (now.hour + 2) // 2 * 2
            if next_hour >= 24:
                next_hour = 0
                next_day = now.day + 1
            else:
                next_day = now.day
            
            next_time = datetime(now.year, now.month, next_day, next_hour, 0, 0)
            wait_seconds = (next_time - now).total_seconds()
            
            print(f"⏰ سيتم إرسال النسخة الاحتياطية التالية في: {next_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            time.sleep(wait_seconds)
            
            send_backup_to_group()
            
        except Exception as e:
            print(f"خطأ في جدولة النسخ الاحتياطي: {e}")
            time.sleep(3600)

def start_telegram_bot():
    print("🚀 بدء تشغيل بوت تليجرام...")
    while True:
        try:
            bot.bot.polling(none_stop=True, interval=0)
        except Exception as e:
            print(f"حدث خطأ في البوت: {e}. إعادة المحاولة بعد 10 ثوان...")
            time.sleep(10)

def is_valid_init_data(init_data_str: str, bot_token: str) -> (bool, dict):
    """
    Validates the initData string from the Telegram Web App using a more
    robust parsing method that handles URL-encoded values.
    """
    try:
        # Use parse_qsl which handles URL decoding of keys and values.
        # It returns a list of (key, value) tuples.
        parsed_qsl = parse_qsl(init_data_str)

        hash_from_telegram = None
        data_for_check_tuples = []
        user_data_str = None

        # Separate the hash from the rest of the data
        for key, value in parsed_qsl:
            if key == 'hash':
                hash_from_telegram = value
            else:
                data_for_check_tuples.append((key, value))
            if key == 'user':
                user_data_str = value

        if not hash_from_telegram or not user_data_str:
            return False, None

        # The data_check_string is formed from the decoded key-value pairs, sorted.
        sorted_tuples = sorted(data_for_check_tuples, key=lambda x: x[0])
        data_check_string = "\n".join([f"{k}={v}" for k, v in sorted_tuples])

        # The rest of the hashing logic remains the same
        secret_key = hmac.new("WebAppData".encode(), bot_token.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        print("--- DEBUG (DECODED): initData Validation ---")
        print(f"data_check_string:\n{data_check_string}")
        print(f"hash_from_telegram: {hash_from_telegram}")
        print(f"calculated_hash:    {calculated_hash}")
        print("--- END DEBUG ---")

        if calculated_hash == hash_from_telegram:
            # The user data string from parse_qsl is already URL-decoded.
            user_data = json.loads(user_data_str)
            return True, user_data

        return False, None
    except Exception as e:
        print(f"Validation error (decoded): {e}")
        return False, None

@app.route('/api/webapp/data', methods=['POST'])
def get_webapp_data():
    """
    API endpoint to fetch all necessary data for the web app.
    Authenticates the user using the initData from Telegram.
    """
    try:
        init_data_str = request.json.get('initData')
        if not init_data_str:
            return jsonify({"ok": False, "error": "initData is required"}), 400

        is_valid, user_data = is_valid_init_data(init_data_str, BOT_TOKEN)

        if not is_valid or not user_data:
            return jsonify({"ok": False, "error": "Invalid initData"}), 403

        user_id = user_data.get('id')

        s = Session()
        try:
            user = s.query(User).filter_by(telegram_id=user_id).first()
            if not user:
                return jsonify({"ok": False, "error": "User not found"}), 404

            # Fetch all necessary data
            orders_q = s.query(Order).options(joinedload(Order.service)).filter_by(user_id=user_id).order_by(Order.ordered_at.desc()).all()
            categories = s.query(Category).order_by(Category.id).all()
            services = s.query(Service).filter_by(is_available=True).order_by(Service.id).all()

            # Serialize data into a clean format for the frontend
            user_info = {
                "id": user.telegram_id,
                "full_name": user.full_name,
                "balance": f"{user.balance:.2f}"
            }

            orders_info = [
                {
                    "id": o.id,
                    "service_name": o.service.name,
                    "quantity": o.quantity,
                    "total_price": f"{o.total_price:.2f}",
                    "status": o.status,
                    "ordered_at": o.ordered_at.strftime('%Y-%m-%d %H:%M')
                } for o in orders_q
            ]

            categories_info = [
                {"id": c.id, "name": c.name, "parent_id": c.parent_id} for c in categories
            ]

            services_info = [
                {
                    "id": s.id,
                    "name": s.name,
                    "description": s.description,
                    "price": f"{s.base_price:.2f}",
                    "category_id": s.category_id
                } for s in services
            ]

            return jsonify({
                "ok": True,
                "user": user_info,
                "orders": orders_info,
                "categories": categories_info,
                "services": services_info
            })
        finally:
            s.close()
    except Exception as e:
        print(f"Error in get_webapp_data: {e}")
        return jsonify({"ok": False, "error": "An internal error occurred"}), 500


if __name__ == "__main__":
    init_db()

    s = Session()
    if not s.query(User).filter_by(is_admin=True).first():
        for admin_id in ADMIN_IDS:
            s.add(User(telegram_id=admin_id, is_admin=True, username=f'admin_{admin_id}'))
        s.commit()
    s.close()

    # Set up ngrok tunnel
    NGROK_AUTH_TOKEN = os.environ.get("NGROK_AUTH_TOKEN")
    if NGROK_AUTH_TOKEN:
        conf.get_default().auth_token = NGROK_AUTH_TOKEN
    else:
        print("Warning: NGROK_AUTH_TOKEN environment variable not set. Ngrok may fail.")

    tunnel = ngrok.connect(FLASK_PORT)
    print(f" * Ngrok tunnel \"{tunnel}\" -> \"http://127.0.0.1:{FLASK_PORT}\"")
    config.WEBAPP_URL = tunnel.public_url

    bot_thread = threading.Thread(target=start_telegram_bot)
    bot_thread.daemon = True
    bot_thread.start()

    backup_thread = threading.Thread(target=backup_scheduler)
    backup_thread.daemon = True
    backup_thread.start()

    server_url = f"http://YOUR_SERVER_IP:{FLASK_PORT}"
    print("✅ تم تشغيل المشروع بنجاح!")
    print(f"لوحة التحكم: {config.WEBAPP_URL}/admin")
    print(f"رابط API: {config.WEBAPP_URL}/api")
    print("⏰ تم تفعيل النسخ الاحتياطي التلقائي كل ساعتين")

    print("🌐 بدء تشغيل لوحة التحكم والـ API ...")
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=False)
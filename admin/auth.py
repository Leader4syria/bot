from flask_login import LoginManager, UserMixin
from database import Session, User
from config import ADMIN_IDS
from utils import send_message_to_user

login_manager = LoginManager()
login_manager.login_view = 'admin.admin_login'

class AdminUser(UserMixin):
    def __init__(self, id):
        self.id = id

    def get_id(self):
        return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    s = Session()
    if int(user_id) in ADMIN_IDS:
        user = s.query(User).filter_by(telegram_id=int(user_id), is_admin=True).first()
        s.close()
        if user:
            return AdminUser(user.telegram_id)
    s.close()
    return None

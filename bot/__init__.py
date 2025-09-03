from telebot import TeleBot
from config import BOT_TOKEN

bot = TeleBot(BOT_TOKEN)
user_states = {}

from . import start, services, profile, referral, admin_commands, callbacks, notifications

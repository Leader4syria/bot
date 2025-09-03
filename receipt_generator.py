from PIL import Image, ImageDraw, ImageFont, ImageOps
import textwrap
import os
from datetime import datetime
from io import BytesIO
from database import Session, User, Order, Payment
from telebot import TeleBot
from config import BOT_TOKEN, GROUP_ID
from sqlalchemy.orm import joinedload
import arabic_reshaper
from bidi.algorithm import get_display

bot = TeleBot(BOT_TOKEN)

TAJAWAL_FONT_PATH = "fonts/Tajawal-Medium.ttf"
TAJAWAL_BOLD_FONT_PATH = "fonts/Tajawal-Bold.ttf"
LOGO_PATH = "fonts/logo.png"

def get_font(font_path, size, default_font=None):
    try:
        return ImageFont.truetype(font_path, size)
    except IOError:
        print(f"تحذير: لم يتم العثور على الخط {font_path}. استخدام الخط الافتراضي.")
        return default_font if default_font else ImageFont.load_default()

def load_png_logo(png_path, size):
    try:
        img = Image.open(png_path)
        img = img.convert("RGBA")
        img = img.resize(size, Image.Resampling.LANCZOS)
        return img
    except FileNotFoundError:
        print(f"خطأ: لم يتم العثور على ملف الشعار {png_path}.")
        return None
    except Exception as e:
        print(f"خطأ في تحميل شعار PNG: {e}")
        return None

def create_rounded_rectangle(draw, xy, radius, fill=None, outline=None, width=1):
    x1, y1, x2, y2 = xy
    draw.rectangle([(x1 + radius, y1), (x2 - radius, y2)], fill=fill, outline=outline, width=width)
    draw.rectangle([(x1, y1 + radius), (x2, y2 - radius)], fill=fill, outline=outline, width=width)
    draw.ellipse([(x1, y1), (x1 + radius * 2, y1 + radius * 2)], fill=fill, outline=outline, width=width)
    draw.ellipse([(x2 - radius * 2, y1), (x2, y1 + radius * 2)], fill=fill, outline=outline, width=width)
    draw.ellipse([(x1, y2 - radius * 2), (x1 + radius * 2, y2)], fill=fill, outline=outline, width=width)
    draw.ellipse([(x2 - radius * 2, y2 - radius * 2), (x2, y2)], fill=fill, outline=outline, width=width)

def format_arabic(text):
    reshaped_text = arabic_reshaper.reshape(text)
    return get_display(reshaped_text)

def create_payment_receipt(user, amount, transaction_id=None):
    try:
        width, height = 800, 1000
        img = Image.new('RGB', (width, height), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        
        font_large = get_font(TAJAWAL_BOLD_FONT_PATH, 56, default_font=ImageFont.load_default())
        font_medium = get_font(TAJAWAL_FONT_PATH, 32, default_font=ImageFont.load_default())
        font_small = get_font(TAJAWAL_FONT_PATH, 26, default_font=ImageFont.load_default())
        font_tiny = get_font(TAJAWAL_FONT_PATH, 20, default_font=ImageFont.load_default())
        
        primary_dark_green = (25, 100, 50)
        secondary_light_green = (90, 170, 100)
        gold_accent = (255, 215, 0)
        text_dark = (10, 30, 10)
        text_light = (60, 100, 60)
        background_gradient_start = (230, 255, 230)
        background_gradient_end = (255, 255, 255)
        
        for i in range(height):
            r = int(background_gradient_start[0] + (background_gradient_end[0] - background_gradient_start[0]) * (i / height))
            g = int(background_gradient_start[1] + (background_gradient_end[1] - background_gradient_start[1]) * (i / height))
            b = int(background_gradient_start[2] + (background_gradient_end[2] - background_gradient_start[2]) * (i / height))
            draw.line((0, i, width, i), fill=(r, g, b))
        
        header_height = 180
        draw.rectangle((0, 0, width, header_height), fill=primary_dark_green)
        for i in range(width // 20):
            draw.polygon([
                (i * 20, header_height - 20),
                (i * 20 + 10, header_height),
                (i * 20 + 20, header_height - 20),
                (i * 20 + 10, header_height - 40)
            ], fill=secondary_light_green)

        title = "إيصال شحن رصيد"
        formatted_title = format_arabic(title)
        draw.text((width / 2, 70), formatted_title, font=font_large, fill=(255, 255, 255), anchor="mm")
        
        logo_size = (120, 120)
        logo_img = load_png_logo(LOGO_PATH, logo_size)
        if logo_img:
            img.paste(logo_img, (int(width / 2 - logo_size[0] / 2), header_height + 30), logo_img)

        market_text = "ماركت حلب"
        formatted_market_text = format_arabic(market_text)
        market_font = get_font(TAJAWAL_BOLD_FONT_PATH, 64, default_font=ImageFont.load_default())
        market_text_bbox = draw.textbbox((0,0), formatted_market_text, font=market_font)
        market_text_width = market_text_bbox[2] - market_text_bbox[0]
        market_text_height = market_text_bbox[3] - market_text_bbox[1]
        
        market_text_x = (width - market_text_width) / 2
        market_text_y = header_height + logo_size[1] + 40
        
        draw.text((market_text_x, market_text_y), formatted_market_text, font=market_font, fill=primary_dark_green)
        
        info_box_x1, info_box_y1 = 80, market_text_y + market_text_height + 50
        info_box_x2, info_box_y2 = width - 80, height - 180
        create_rounded_rectangle(draw, (info_box_x1, info_box_y1, info_box_x2, info_box_y2), 20, 
                                 fill=(255, 255, 255, 200), outline=secondary_light_green, width=3)
        
        y_position = info_box_y1 + 40
        padding_right = info_box_x2 - 40
        padding_left = info_box_x1 + 40
        line_height = 50
        
        info_items = [
            ("اسم المستخدم:", user.full_name or user.username or 'غير معروف'),
            ("معرف التليجرام:", user.telegram_id),
            ("تاريخ العملية:", datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            ("نوع العملية:", "شحن رصيد"),
            ("المبلغ:", f"${amount:.2f}", gold_accent),
        ]
        
        if transaction_id:
            info_items.insert(4, ("رقم المرجع:", transaction_id))
        
        for label, value, *color_override in info_items:
            current_color = color_override[0] if color_override else text_dark
            formatted_label = format_arabic(label)
            
            formatted_value = format_arabic(str(value)) if isinstance(value, str) else str(value)
            
            draw.text((padding_right, y_position), formatted_label, font=font_medium, fill=text_light, anchor="ra")
            draw.text((padding_left, y_position), formatted_value, font=font_medium, fill=current_color)
            y_position += line_height
            
        status_box_y = y_position + 30
        create_rounded_rectangle(draw, (info_box_x1 + 20, status_box_y, info_box_x2 - 20, status_box_y + 70), 15,
                                 fill=gold_accent, outline=primary_dark_green, width=2)
        formatted_status = format_arabic("حالة العملية: مكتمل")
        draw.text((width / 2, status_box_y + 35), formatted_status, font=font_large, fill=primary_dark_green, anchor="mm")
        
        footer_height = 120
        draw.rectangle((0, height - footer_height, width, height), fill=primary_dark_green)
        for i in range(width // 20):
            draw.polygon([
                (i * 20, height - footer_height + 20),
                (i * 20 + 10, height - footer_height),
                (i * 20 + 20, height - footer_height + 20),
                (i * 20 + 10, height - footer_height + 40)
            ], fill=secondary_light_green)

        footer_text = "شكرًا لثقتك بماركت حلب - @Market963_bot"
        formatted_footer = format_arabic(footer_text)
        draw.text((width / 2, height - footer_height / 2 + 10), formatted_footer, font=font_small, fill=(255, 255, 255), anchor="mm")
        
        img_byte_arr = BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        return img_byte_arr
    
    except Exception as e:
        print(f"خطأ في إنشاء الإيصال: {e}")
        return None

def create_order_receipt(user, order):
    try:
        width, height = 800, 1100
        img = Image.new('RGB', (width, height), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        
        font_large = get_font(TAJAWAL_BOLD_FONT_PATH, 56, default_font=ImageFont.load_default())
        font_medium = get_font(TAJAWAL_FONT_PATH, 32, default_font=ImageFont.load_default())
        font_small = get_font(TAJAWAL_FONT_PATH, 26, default_font=ImageFont.load_default())
        font_tiny = get_font(TAJAWAL_FONT_PATH, 20, default_font=ImageFont.load_default())
        
        primary_dark_green = (25, 100, 50)
        secondary_light_green = (90, 170, 100)
        gold_accent = (255, 215, 0)
        text_dark = (10, 30, 10)
        text_light = (60, 100, 60)
        background_gradient_start = (230, 255, 230)
        background_gradient_end = (255, 255, 255)
        
        for i in range(height):
            r = int(background_gradient_start[0] + (background_gradient_end[0] - background_gradient_start[0]) * (i / height))
            g = int(background_gradient_start[1] + (background_gradient_end[1] - background_gradient_start[1]) * (i / height))
            b = int(background_gradient_start[2] + (background_gradient_end[2] - background_gradient_start[2]) * (i / height))
            draw.line((0, i, width, i), fill=(r, g, b))
        
        header_height = 180
        draw.rectangle((0, 0, width, header_height), fill=primary_dark_green)
        for i in range(width // 20):
            draw.polygon([
                (i * 20, header_height - 20),
                (i * 20 + 10, header_height),
                (i * 20 + 20, header_height - 20),
                (i * 20 + 10, header_height - 40)
            ], fill=secondary_light_green)

        title = "إيصال طلب خدمة"
        formatted_title = format_arabic(title)
        draw.text((width / 2, 70), formatted_title, font=font_large, fill=(255, 255, 255), anchor="mm")
        
        logo_size = (120, 120)
        logo_img = load_png_logo(LOGO_PATH, logo_size)
        if logo_img:
            img.paste(logo_img, (int(width / 2 - logo_size[0] / 2), header_height + 30), logo_img)

        market_text = "ماركت حلب"
        formatted_market_text = format_arabic(market_text)
        market_font = get_font(TAJAWAL_BOLD_FONT_PATH, 64, default_font=ImageFont.load_default())
        market_text_bbox = draw.textbbox((0,0), formatted_market_text, font=market_font)
        market_text_width = market_text_bbox[2] - market_text_bbox[0]
        market_text_height = market_text_bbox[3] - market_text_bbox[1]
        
        market_text_x = (width - market_text_width) / 2
        market_text_y = header_height + logo_size[1] + 40
        
        draw.text((market_text_x, market_text_y), formatted_market_text, font=market_font, fill=primary_dark_green)
        
        info_box_x1, info_box_y1 = 80, market_text_y + market_text_height + 50
        info_box_x2, info_box_y2 = width - 80, height - 180
        create_rounded_rectangle(draw, (info_box_x1, info_box_y1, info_box_x2, info_box_y2), 20, 
                                 fill=(255, 255, 255, 200), outline=secondary_light_green, width=3)
        
        y_position = info_box_y1 + 40
        padding_right = info_box_x2 - 40
        padding_left = info_box_x1 + 40
        line_height = 50
        
        info_items = [
            ("اسم المستخدم:", user.full_name or user.username or 'غير معروف'),
            ("معرف التليجرام:", user.telegram_id),
            ("تاريخ الطلب:", order.ordered_at.strftime('%Y-%m-%d %H:%M:%S')),
            ("رقم الطلب:", order.id),
            ("الخدمة:", order.service.name if order.service else 'غير معروف'),
            ("الكمية:", order.quantity),
            ("السعر الإجمالي:", f"${order.total_price:.2f}", gold_accent),
            ("الرابط/المعرف:", order.link_or_id),
        ]
        
        for label, value, *color_override in info_items:
            current_color = color_override[0] if color_override else text_dark
            formatted_label = format_arabic(label)

            formatted_value = format_arabic(str(value)) if isinstance(value, str) else str(value)
            
            draw.text((padding_right, y_position), formatted_label, font=font_medium, fill=text_light, anchor="ra")
            draw.text((padding_left, y_position), formatted_value, font=font_medium, fill=current_color)
            y_position += line_height
        
        footer_height = 120
        draw.rectangle((0, height - footer_height, width, height), fill=primary_dark_green)
        for i in range(width // 20):
            draw.polygon([
                (i * 20, height - footer_height + 20),
                (i * 20 + 10, height - footer_height),
                (i * 20 + 20, height - footer_height + 20),
                (i * 20 + 10, height - footer_height + 40)
            ], fill=secondary_light_green)

        footer_text = "شكرًا لثقتك بماركت حلب - @Market963_bot"
        formatted_footer = format_arabic(footer_text)
        draw.text((width / 2, height - footer_height / 2 + 10), formatted_footer, font=font_small, fill=(255, 255, 255), anchor="mm")
        
        img_byte_arr = BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        return img_byte_arr
    
    except Exception as e:
        print(f"خطأ في إنشاء إيصال الطلب: {e}")
        return None

def send_payment_receipt(user_id, amount, transaction_id=None):
    try:
        s = Session()
        user = s.query(User).filter_by(telegram_id=user_id).first()
        if not user:
            print(f"المستخدم غير موجود: {user_id}")
            return False
        
        receipt = create_payment_receipt(user, amount, transaction_id)
        if not receipt:
            print("فشل إنشاء الإيصال")
            return False
        
        bot.send_photo(
            user_id,
            receipt,
            caption=f"تم شحن رصيدك بمبلغ ${amount:.2f} بنجاح.\nرصيدك الحالي: ${user.balance:.2f}"
        )
        
        if GROUP_ID:
            receipt.seek(0) 
            bot.send_photo(
                GROUP_ID,
                receipt,
                caption=f"تم شحن رصيد للمستخدم {user.full_name or user.username} (ID: {user.telegram_id})\nالمبلغ: ${amount:.2f}"
            )
        
        return True
    
    except Exception as e:
        print(f"خطأ في إرسال إيصال الدفع: {e}")
        return False
    finally:
        s.close()

def send_order_receipt(user_id, order_id):
    try:
        s = Session()
        user = s.query(User).filter_by(telegram_id=user_id).first()
        order = s.query(Order).options(joinedload(Order.service)).filter_by(id=order_id).first()
        
        if not user or not order:
            print(f"المستخدم أو الطلب غير موجود: {user_id}, {order_id}")
            return False
        
        receipt = create_order_receipt(user, order)
        if not receipt:
            print("فشل إنشاء إيصال الطلب")
            return False
        
        bot.send_photo(
            user_id,
            receipt,
            caption=f"تم تقديم طلبك بنجاح!\nرقم الطلب: {order.id}\nالخدمة: {order.service.name}\nالسعر: ${order.total_price:.2f}"
        )
        
        if GROUP_ID:
            receipt.seek(0)
            bot.send_photo(
                GROUP_ID,
                receipt,
                caption=f"طلب جديد من {user.full_name or user.username} (ID: {user.telegram_id})\nرقم الطلب: {order.id}\nالخدمة: {order.service.name}\nالسعر: ${order.total_price:.2f}"
            )
        
        return True
    
    except Exception as e:
        print(f"خطأ في إرسال إيصال الطلب: {e}")
        return False
    finally:
        s.close()

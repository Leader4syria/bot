import requests
import time
from database import Session, ServiceMapping, ServiceProvider
from sqlalchemy.orm import joinedload

class SMMProvider:
    def __init__(self, provider_id=None):
        self.session = Session()
        if provider_id:
            self.provider = self.session.query(ServiceProvider).get(provider_id)
        else:
            self.provider = self.session.query(ServiceProvider).filter_by(is_active=True).first()
        
        if not self.provider:
            raise Exception("لا يوجد مزود خدمة نشط")
    
    def add_order(self, service_mapping_id, link, quantity):
        try:
            mapping = self.session.query(ServiceMapping).options(
                joinedload(ServiceMapping.service)
            ).get(service_mapping_id)
            
            if not mapping:
                return {"error": "تعيين الخدمة غير موجود"}
            
            if quantity < mapping.min_quantity:
                return {"error": f"الكمية أقل من الحد الأدنى ({mapping.min_quantity})"}
            
            if quantity > mapping.max_quantity:
                return {"error": f"الكمية أكبر من الحد الأقصى ({mapping.max_quantity})"}
            
            balance_result = self.get_balance()
            if 'error' in balance_result:
                return {"error": f"خطأ في التحقق من الرصيد: {balance_result['error']}"}
            
            provider_price = mapping.service.base_price / mapping.price_multiplier
            estimated_cost = (quantity / 1000) * provider_price
            
            if float(balance_result.get('balance', 0)) < estimated_cost:
                return {"error": f"رصيد المزود غير كافٍ. الرصيد الحالي: {balance_result.get('balance', 0)}، التكلفة التقريبية: {estimated_cost}"}
            
            payload = {
                "key": self.provider.api_key,
                "action": "add",
                "service": mapping.provider_service_id,
                "link": link,
                "quantity": quantity
            }
            
            response = requests.post(self.provider.api_url, data=payload)
            result = response.json()
            
            return result
            
        except Exception as e:
            return {"error": f"خطأ في الإضافة: {str(e)}"}
        finally:
            self.session.close()
    
    def get_order_status(self, order_id):
        try:
            payload = {
                "key": self.provider.api_key,
                "action": "status",
                "order": order_id
            }
            
            response = requests.post(self.provider.api_url, data=payload)
            return response.json()
            
        except Exception as e:
            return {"error": f"خطأ في الحصول على الحالة: {str(e)}"}
    
    def get_services(self):
        try:
            payload = {
                "key": self.provider.api_key,
                "action": "services"
            }
            
            response = requests.post(self.provider.api_url, data=payload)
            return response.json()
            
        except Exception as e:
            return {"error": f"خطأ في الحصول على الخدمات: {str(e)}"}
    
    def get_balance(self):
        try:
            payload = {
                "key": self.provider.api_key,
                "action": "balance"
            }
            
            response = requests.post(self.provider.api_url, data=payload)
            return response.json()
            
        except Exception as e:
            return {"error": f"خطأ في الحصول على الرصيد: {str(e)}"}

def process_automatic_orders():
    from database import Session, Order, ServiceMapping
    from bot_handlers import notify_user_order_status_update
    
    session = Session()
    try:
        orders = session.query(Order).options(
            joinedload(Order.service)
        ).filter(
            Order.status == 'Pending',
            Order.service.has(ServiceMapping.id.isnot(None))
        ).all()
        
        for order in orders:
            mapping = session.query(ServiceMapping).filter_by(
                service_id=order.service_id
            ).first()
            
            if mapping:
                provider = SMMProvider(mapping.provider_id)
                result = provider.add_order(
                    mapping.id, 
                    order.link_or_id, 
                    order.quantity
                )
                
                if 'order' in result:
                    order.status = 'Processing'
                    order.provider_order_id = result['order']
                    session.commit()
                    
                    print(f"تم إرسال الطلب {order.id} إلى المزود، رقم الطلب: {result['order']}")
                
                elif 'error' in result:
                    print(f"خطأ في الطلب {order.id}: {result['error']}")
            
            time.sleep(2)
            
    except Exception as e:
        print(f"خطأ في معالجة الطلبات التلقائية: {e}")
    finally:
        session.close()

def check_orders_status():
    from database import Session, Order
    from bot_handlers import notify_user_order_status_update
    
    session = Session()
    try:
        orders = session.query(Order).filter(
            Order.status == 'Processing',
            Order.provider_order_id.isnot(None)
        ).all()
        
        for order in orders:
            mapping = session.query(ServiceMapping).filter_by(
                service_id=order.service_id
            ).first()
            
            if mapping:
                provider = SMMProvider(mapping.provider_id)
                status = provider.get_order_status(order.provider_order_id)
                
                if status.get('status') == 'Completed':
                    order.status = 'Completed'
                    session.commit()
                    
                    notify_user_order_status_update(order.id, 'Completed', order.user_id)
                    print(f"تم إكمال الطلب {order.id}")
                
                elif status.get('status') == 'Canceled':
                    order.status = 'Canceled'
                    session.commit()
                    
                    print(f"تم إلغاء الطلب {order.id}")
            
            time.sleep(1)
            
    except Exception as e:
        print(f"خطأ في التحقق من حالة الطلبات: {e}")
    finally:
        session.close()

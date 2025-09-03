from flask import Flask, render_template, jsonify, request
from pyngrok import ngrok
from pyngrok.exception import PyngrokNgrokError
import os
import atexit

# Set up Flask app
app = Flask(__name__, template_folder='.', static_folder='.')
app.config["TEMPLATES_AUTO_RELOAD"] = True

public_url = None
try:
    # Start ngrok and get the public URL
    # Ensure the port number matches the port Flask is running on
    public_url = ngrok.connect(5000)
    print(f" * ngrok tunnel \"{public_url}\" -> \"http://127.0.0.1:5000\"")
    # Update the global variable
    app.config['NGROK_URL'] = public_url
except PyngrokNgrokError as e:
    print(f"Error starting ngrok: {e}")
    print("Please check your ngrok configuration and ensure you have a valid authtoken.")
    print("You can get an authtoken from https://dashboard.ngrok.com/get-started/your-authtoken")
    public_url = None

def shutdown_ngrok():
    if public_url:
        print("Shutting down ngrok tunnels...")
        ngrok.disconnect(public_url)
        print("ngrok tunnels shut down.")

atexit.register(shutdown_ngrok)

@app.route('/')
def index():
    return render_template('services.html', ngrok_url=app.config['NGROK_URL'])

@app.route('/services')
def services():
    return render_template('services.html', ngrok_url=app.config['NGROK_URL'])

@app.route('/orders')
def orders():
    return render_template('orders.html', ngrok_url=app.config['NGROK_URL'])

@app.route('/wallet')
def wallet():
    return render_template('wallet.html', ngrok_url=app.config['NGROK_URL'])

@app.route('/payments')
def payments():
    return render_template('payments.html', ngrok_url=app.config['NGROK_URL'])

@app.route('/get_ngrok_url')
def get_ngrok_url():
    return jsonify({'url': app.config['NGROK_URL']})

@app.route('/api/services')
def api_services():
    from database import Session, Service
    s = Session()
    services = s.query(Service).filter_by(is_available=True).all()
    s.close()
    return jsonify([{
        'id': service.id,
        'name': service.name,
        'description': service.description,
        'base_price': float(service.base_price),
        'base_quantity': service.base_quantity
    } for service in services])

if __name__ == "__main__":
    app.run(port=5000)

from bson import ObjectId
from flask import Flask, url_for, redirect, g, session
from dotenv import load_dotenv
import os
from flask_login import current_user
from flask_socketio import SocketIO, join_room
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
import time
import logging
from flask_mail import Mail
from flask_debugtoolbar import DebugToolbarExtension

from pymongo import MongoClient


load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['MAIL_SERVER']=os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = os.getenv('MAIL_PORT')
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

db = MongoClient(os.getenv('MONGO_URI'))['uber']
active_orders = db['active_orders']

toolbar = DebugToolbarExtension(app)
scheduler = BackgroundScheduler()

class ResponseTimeMiddleware(object):
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        start_time = time.time()
        response = self.app(environ, start_response)
        end_time = time.time()
        response_time = end_time - start_time
        app.logger.info(f'Response time: {response_time} seconds')
        return response
    

socketio = SocketIO(app=app, Engineio_logger=True, logger=True)
CORS(app, resources={r"/clients/socket.io/*": {"origins": "http://localhost:5000"}})
app.wsgi_app = ResponseTimeMiddleware(app.wsgi_app)
logging.basicConfig(filename='app.log', level=logging.INFO)
logger = logging.getLogger('performance_logger')
mail = Mail(app)

def fetch_order_status(order_id, user_id):
    try:
        order = active_orders.find_one({'_id': ObjectId(order_id)})
        if order is None:
            logging.info(f"Order {order_id} not found")
            scheduler.remove_job(fetch_order_status)
            return
        order_status = order['status']
        logging.info(f"Order {order_id} status: {order_status}")
        if order_status == 'accepted':
            order_driver = order['driver_name']
            scheduler.remove_job(fetch_order_status)
            socketio.emit("order_accepted", {'order_id': order_id, "order_driver": order_driver}, namespace='/clients', to=user_id)
    except Exception as e:
        logging.info(f"Exception: {str(e)}")
        scheduler.remove_job(fetch_order_status)

@app.route('/')
def index():
    return redirect(url_for('authentication.login'))

@socketio.on('connect', namespace='/clients')
def client_connect():
    print('Client connected')
    room_id = current_user.id
    join_room(room_id)
    logging.info(f"Client {current_user.username} connected to room {room_id}")

@socketio.on('start_status_check', namespace='/clients')
def start_status_check(data):
    logging.info(f"Starting status check for order {data['order_id']}")
    scheduler.add_job(fetch_order_status, 'interval', seconds=15, args=[data['order_id'], current_user.id])
    scheduler.start()

@socketio.on('connect', namespace='/ride_chat')
def handle_connect():
    logging.info(f"{current_user.username} connected to ride chat")

@socketio.on('join', namespace='/ride_chat')
def handle_join(data):
    room = data['room_id']
    join_room(room)
    logging.info(f"{current_user.username} joined room {room}")

@socketio.on('send_message', namespace='/ride_chat')
def handle_send_message(data):
    logging.info(f"Sending message to room {data['room_id']}")
    message = data['message']
    socketio.emit('receive_message', {'message': message}, namespace='/ride_chat', to=data['room_id'])

@socketio.on('ride_end', namespace='/ride_chat')
def handle_ride_end(data):
    logging.info(f"Ride ended in room {data['room_id']}")
    socketio.emit('ride_ended', namespace='/ride_chat', to=data['room_id'])

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()
    
if __name__ == '__main__':
    from authentication import authentication
    from clients import clients
    from drivers import drivers
    app.register_blueprint(authentication)
    app.register_blueprint(clients)
    app.register_blueprint(drivers)
    socketio.run(app, log_output=True, debug=True)

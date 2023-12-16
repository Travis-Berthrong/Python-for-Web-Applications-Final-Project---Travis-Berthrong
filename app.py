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

from pymongo import MongoClient


load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

db = MongoClient(os.getenv('MONGO_URI'))['uber']
active_orders = db['active_orders']

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

def fetch_order_status(order_id, user_id):
    try:
        order = active_orders.find_one({'_id': ObjectId(order_id)})
        order_status = order['status']
        print(f"Order status: {order_status}")
        if order_status == 'accepted':
            order_driver = order['driver_name']
            scheduler.remove_all_jobs()
            socketio.emit("order_accepted", {'order_id': order_id, "order_driver": order_driver}, namespace='/clients', to=user_id)
    except Exception as e:
        print("fetch_order_status error: ", e)

@app.route('/')
def index():
    return redirect(url_for('authentication.login'))

@socketio.on('connect', namespace='/clients')
def client_connect():
    print('Client connected')
    room_id = current_user.id
    join_room(room_id)
    print(f"Client {current_user.id} joined room {current_user.id}")

@socketio.on('start_status_check', namespace='/clients')
def start_status_check(data):
    print(f"Starting status check for order {data['order_id']}")
    scheduler.add_job(fetch_order_status, 'interval', seconds=15, args=[data['order_id'], current_user.id])
    scheduler.start()

@socketio.on('connect', namespace='/ride_chat')
def handle_connect():
    print('connected to ride chat')

@socketio.on('join', namespace='/ride_chat')
def handle_join(data):
    room = data['room_id']
    join_room(room)
    print(f'{current_user.username} joined room ', room)

@socketio.on('send_message', namespace='/ride_chat')
def handle_send_message(data):
    print(f"Sending message to room {data['room_id']}")
    message = data['message']
    socketio.emit('receive_message', {'message': message}, namespace='/ride_chat', to=data['room_id'])

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

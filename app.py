from flask import Flask, url_for, redirect
from dotenv import load_dotenv
import os

load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

@app.route('/')
def index():
    return redirect(url_for('authentication.login'))


if __name__ == '__main__':
    from authentication import authentication
    app.register_blueprint(authentication)
    from clients import clients
    app.register_blueprint(clients)
    app.run(debug=True)

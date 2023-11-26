from flask import Flask
from dotenv import load_dotenv
import os

load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024


if __name__ == '__main__':
    from authentication import authentication
    app.register_blueprint(authentication)
    app.run(debug=True)

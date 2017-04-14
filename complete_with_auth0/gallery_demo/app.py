from flask import Flask, render_template, redirect, url_for, send_from_directory, request, session
from flask_bootstrap import Bootstrap
from PIL import Image
from werkzeug.utils import secure_filename
from dotenv import Dotenv
from functools import wraps
import os
import constants
import requests

# Load Env variables
env = None

try:
    env = Dotenv('./.env')
except IOError:
    env = os.environ

app = Flask(__name__)
app.secret_key = env['SECRET_KEY']
Bootstrap(app)

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
images_directory = os.path.join(APP_ROOT, 'images')
thumbnails_directory = os.path.join(APP_ROOT, 'thumbnails')
if not os.path.isdir(images_directory):
    os.mkdir(images_directory)
if not os.path.isdir(thumbnails_directory):
    os.mkdir(thumbnails_directory)

# Requires authentication decorator
def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if is_logged_in():
            return f(*args, **kwargs)
        return redirect('/')
    return decorated

def is_logged_in():
    return constants.PROFILE_KEY in session

@app.route('/')
def index():
    return render_template('index.html', env=env, logged_in=is_logged_in())

@app.route('/gallery')
def gallery():
    thumbnail_names = os.listdir('./thumbnails')
    return render_template('gallery.html', thumbnail_names=thumbnail_names)

@app.route('/thumbnails/<filename>')
def thumbnails(filename):
    return send_from_directory('thumbnails', filename)

@app.route('/images/<filename>')
def images(filename):
    return send_from_directory('images', filename)

@app.route('/public/<path:filename>')
def static_files(filename):
    return send_from_directory('./public', filename)

@app.route('/upload', methods=['GET', 'POST'])
@requires_auth
def upload():
    if request.method == 'POST':
        for upload in request.files.getlist('images'):
            filename = upload.filename
            # Always a good idea to secure a filename before storing it
            filename = secure_filename(filename)
            # This is to verify files are supported
            ext = os.path.splitext(filename)[1][1:].strip().lower()
            if ext in set(['jpg', 'jpeg', 'png']):
                print('File supported moving on...')
            else:
                return render_template('error.html', message='Uploaded files are not supported...')
            destination = '/'.join([images_directory, filename])
            # Save original image
            upload.save(destination)
            # Save a copy of the thumbnail image
            image = Image.open(destination)
            image.thumbnail((300, 170))
            image.save('/'.join([thumbnails_directory, filename]))
        return redirect(url_for('gallery'))
    return render_template('upload.html', user=session[constants.PROFILE_KEY])

@app.route('/logout')
@requires_auth
def logout():
    session.clear()
    return redirect('https://{auth0_domain}/v2/logout?client_id={auth0_client_id}&returnTo={app_url}'\
        .format(auth0_domain=env[constants.AUTH0_DOMAIN], auth0_client_id=env[constants.AUTH0_CLIENT_ID],
            app_url='http://localhost:3000'))

@app.route('/callback')
def callback_handling():
    code = request.args.get(constants.CODE_KEY)
    json_header = {constants.CONTENT_TYPE_KEY: constants.APP_JSON_KEY}
    token_url = 'https://{auth0_domain}/oauth/token'.format(
        auth0_domain=env[constants.AUTH0_DOMAIN])
    token_payload = {
        constants.CLIENT_ID_KEY: env[constants.AUTH0_CLIENT_ID],
        constants.CLIENT_SECRET_KEY: env[constants.AUTH0_CLIENT_SECRET],
        constants.REDIRECT_URI_KEY: env[constants.AUTH0_CALLBACK_URL],
        constants.CODE_KEY: code,
        constants.GRANT_TYPE_KEY: constants.AUTHORIZATION_CODE_KEY
    }

    token_info = requests.post(token_url, json=token_payload,
        headers=json_header).json()

    user_url = 'https://{auth0_domain}/userinfo?access_token={access_token}'\
        .format(auth0_domain=env[constants.AUTH0_DOMAIN],
            access_token=token_info[constants.ACCESS_TOKEN_KEY])

    user_info = requests.get(user_url).json()
    session[constants.PROFILE_KEY] = user_info
    return redirect(url_for('upload'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 3000))

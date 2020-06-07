import asyncio
from datetime import datetime, timezone
from datetime import timedelta
import json
import uuid
import os
import requests

from sanic import Sanic
from sanic.log import logger
from sanic import response
from sanic_cors import CORS

production = True and 'DEV8dac6d02a913' not in os.environ
basedir = '/vagrant'
basedir = basedir if production else os.getcwd()
TOKEN = None
LOG_SETTINGS = dict(
    version=1,
    disable_existing_loggers=False,
    loggers={
        "sanic.root": {"level": "INFO", "handlers": ["consolefile"]},
        "sanic.error": {
            "level": "INFO",
            "handlers": ["error_consolefile"],
            "propagate": True,
            "qualname": "sanic.error",
        },
        "sanic.access": {
            "level": "INFO",
            "handlers": ["access_consolefile"],
            "propagate": True,
            "qualname": "sanic.access",
        },
    },
    handlers={
        "consolefile": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "when": 'D',
            "interval": 7,
            "backupCount": 10,
            'filename': os.path.join(basedir, "backend", "console.log"),
            "formatter": "generic",
        },
        "error_consolefile": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "when": 'D',
            "interval": 7,
            "backupCount": 10,
            'filename': os.path.join(basedir, "backend", "error.log"),
            "formatter": "generic",
        },
        "access_consolefile": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "when": 'D',
            "interval": 7,
            "backupCount": 10,
            'filename': os.path.join(basedir, "backend", "access.log"),
            "formatter": "access",
        },
    },
    formatters={
        "generic": {
            "format": "%(asctime)s [%(process)d] [%(levelname)s] %(message)s",
            "datefmt": "[%Y-%m-%d %H:%M:%S %z]",
            "class": "logging.Formatter",
        },
        "access": {
            "format": "%(asctime)s - (%(name)s)[%(levelname)s][%(host)s]: "
                      + "%(request)s %(message)s %(status)d %(byte)d",
            "datefmt": "[%Y-%m-%d %H:%M:%S %z]",
            "class": "logging.Formatter",
        },
    },
)

if production:
    app = Sanic("store", log_config=LOG_SETTINGS)
else:
    app = Sanic("store")
CORS(app)

config = {"upload": os.path.join(basedir, "uploads", "Responses")}
try:
    with open(os.path.join(basedir, "uploads", "apiKey.txt"), "r") as fp:
        ACCESS_KEY = fp.read()
except FileNotFoundError:
    ACCESS_KEY = None

try:
    with open(os.path.join(basedir, 'dynamic_map.json')) as fp:
        dynamic_map = json.load(fp)
except FileNotFoundError:
    dynamic_map = {}

pending_tokens = {}

sem = None
@app.listener('before_server_start')
def before_start(sanic, loop):
    global sem
    sem = asyncio.Semaphore(100)


@app.route("/")
async def main(request):
    return response.json({"hello": "world"})


@app.route("/register", methods=["GET", ])
async def register(request):
    args = request.args
    if 'token' not in args:
        return response.json({'status': 'not_authorized'}, 403)
    if args['token'][0] != TOKEN:
        return response.json({'status': 'not_authorized_token'}, 403)
    logger.info(request.url)
    callback_url = request.args['callback_url'][0]
    if production:
        # Prevent accidental registration of local urls on production
        # server
        local_hosts = ["127.0.0.1", "//localhost"]
        if any([key in callback_url for key in local_hosts]):
            return response.json({'status': 'not_authorized_url'}, 403)
    client_id = uuid.uuid4().hex
    dynamic_map[client_id] = dict(callback_url=callback_url)
    with open(os.path.join(basedir, 'dynamic_map.json'), 'wt') as fp:
        json.dump(dynamic_map, fp)
    logger.info(f"New client: {client_id} Callback: {callback_url}")
    return response.json({"client_id": client_id})


async def flush_tokens():
    remove_tokens = []
    for k, v in pending_tokens.items():
        if v < datetime.now(timezone.utc):
            remove_tokens.append(k)
    for token in remove_tokens:
        logger.info('remove: {}'.format(token))
        del pending_tokens[token]


@app.route("/token", methods=["GET"])
async def generate_token(request):
    logger.info(request.url)
    is_authorized = False
    if 'client_id' in request.args:
        if request.args['client_id'][0] in dynamic_map:
            is_authorized = True
    if not is_authorized:
        return response.json({'status': 'not_authorized'}, 403)
    client_auth_token = uuid.uuid4().hex
    expiry_minutes = 90
    if 'expiry_minutes' in request.args:
        expiry_minutes = int(request.args['expiry_minutes'][0])
    # token expiration delay
    expiry_time = timedelta(minutes=expiry_minutes)
    expiration = datetime.now(timezone.utc) + expiry_time
    logger.info(f"Token: {client_auth_token} Expiration: {expiration}")
    pending_tokens[client_auth_token] = expiration
    callback_url = dynamic_map[request.args['client_id'][0]]["callback_url"]
    callback_url += "?auth_token=" + client_auth_token
    callback_url += "&expiry=" + str(expiration)
    if "participant_id" in request.args:
        callback_url += "&participant_id=" + request.args["participant_id"][0]
    return response.redirect(callback_url)


@app.route("/submit", methods=["POST", ])
async def submit(request):
    """
    See the test_serve file for an example of how to encode this
    """
    if "auth_token" not in request.form:
        return response.json({'status': 'Unauthorized'}, 403)
    token = request.form['auth_token'][0]
    if token not in pending_tokens:
        return response.json({'status': 'Unauthorized token'}, 403)
    now = datetime.now(timezone.utc)
    if now > pending_tokens[token]:
        await flush_tokens()
        return response.json({'status': 'Token expired'}, 403)
    logger.info(f"Token: {token}")
    request_ip = request.remote_addr or request.ip
    if ACCESS_KEY is not None:
        response_ip = requests.get(
            'http://api.ipstack.com/'+request_ip+'?access_key='+ACCESS_KEY)
        logger.info(response_ip.json())
    data_file = request.files.get('file', None)
    if data_file is not None:
        filename = os.path.join(config['upload'],
                                str(now).replace(' ', 'T') + '_' + data_file.name)
        with open(filename, "wb") as fp:
            fp.write(data_file.body)
    if "responses" in request.form:
        responses = json.loads(request.form['responses'][0])
        filename = os.path.join(config['upload'],
                                str(now).replace(' ', 'T') + "_messages.json")
        with open(filename, "wt") as fp:
            json.dump(responses, fp, indent=2, sort_keys=False)
    await flush_tokens()
    return response.json({"status": "accepted"})


if __name__ == "__main__":
    logger.info("Starting backend")
    if TOKEN is None:
        TOKEN = uuid.uuid4().hex
        logger.info(f"TOKEN={TOKEN}")
    if not os.path.exists(config["upload"]):
        os.makedirs(config["upload"])
    app.run(host="0.0.0.0", port=8000)

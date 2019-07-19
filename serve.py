import asyncio
from datetime import datetime
from datetime import timedelta
import math
import uuid
import sys
import os

from sanic import Sanic
from sanic.log import logger, error_logger, access_logger
from sanic import response
from sanic.response import json, text
from sanic_cors import CORS, cross_origin

LOG_SETTINGS = dict(
	version=1,
	disable_existing_loggers=False,
	loggers={
		"sanic.root": {"level": "INFO", "handlers": ["console", "consolefile"]},
		"sanic.error": {
			"level": "INFO",
			"handlers": ["error_console", "error_consolefile"],
			"propagate": True,
			"qualname": "sanic.error",
		},
		"sanic.access": {
			"level": "INFO",
			"handlers": ["access_console", "access_consolefile"],
			"propagate": True,
			"qualname": "sanic.access",
		},
	},
	handlers={
		"console": {
			"class": "logging.StreamHandler",
			"formatter": "generic",
			"stream": sys.stdout,
		},
		"error_console": {
			"class": "logging.StreamHandler",
			"formatter": "generic",
			"stream": sys.stderr,
		},
		"access_console": {
			"class": "logging.StreamHandler",
			"formatter": "access",
			"stream": sys.stdout,
		},
		"consolefile": {
			'class': 'logging.FileHandler',
			'filename': "/vagrant/console.log",
			"formatter": "generic",
		},
		"error_consolefile": {
			'class': 'logging.FileHandler',
			'filename': "/vagrant/error.log",
			"formatter": "generic",
		},
		"access_consolefile": {
			'class': 'logging.FileHandler',
			'filename': "/vagrant/access.log",
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

max_per_bin = 1  # max data required per bin
slop_factor = 1  # allow up to this many tokens
expiry_time = timedelta(minutes=20)  # token expiration delay

current_bins = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
pending_bins = current_bins.copy()
pending_tokens = {}

app = Sanic("voiceback", log_config=LOG_SETTINGS)
CORS(app)

config = {}
config["upload"] = "./uploads/VoiceData"

@app.route("/")
async def main(request):
	return json({"hello": "world"})

async def clear_globals():
	global current_bins
	global pending_bins
	global pending_tokens
	current_bins = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
	pending_bins = current_bins.copy()
	pending_tokens = {}

@app.route("/reset")
async def reset(request):
	global pending_tokens
	await clear_globals()
	return json(pending_bins)

@app.route("/reset", methods=["POST",])
async def post_reset(request):
	global max_per_bin
	global slop_factor
	global expiry_time
	max_per_bin = request.json['max_per_bin']  # max data required per bin
	slop_factor = request.json['slop_factor']  # allow up to this many tokens
	expiry_time = timedelta(minutes=request.json['expiry_mins'])  # token expiration delay
	await clear_globals()
	return json({"status": "reset-post"})

async def flush_tokens():
	remove_tokens = []
	for k, v in pending_tokens.items():
		if v[0] < datetime.now():
			rbin = v[1]
			pending_bins[rbin] = max(0, pending_bins[rbin] - 1)
			remove_tokens.append(k)
	for token in remove_tokens:
		logger.info('remove: {}'.format(token))
		del pending_tokens[token]


async def qualified(data):
	logger.info((current_bins, pending_bins, pending_tokens))
	total_score = 'https://raw.githubusercontent.com/ReproNim/schema' \
				   '-standardization/master/activities/PHQ-9/items' \
					   '/phq9_total_score.jsonld'
	ts = data[total_score]
	if ts < 0 or ts > 27:
		return False, None
	rbin = min(4, math.ceil(max(ts - 5, 0)/5))
	if current_bins[rbin] < max_per_bin:
		await flush_tokens()
		if pending_bins[rbin] >= (max_per_bin + slop_factor):
			return False, None
		pending_bins[rbin] += 1
		return True, rbin
	return False, None


async def get_token(rbin):
	token = str(uuid.uuid4())
	expiration = datetime.now() + expiry_time
	pending_tokens[token] = expiration, rbin
	logger.info('create: {0}-{1}-{2}'.format(token, expiration, rbin))
	return token, expiration


@app.listener('before_server_start')
async def before_start(app, uvloop):
	sem = await asyncio.Semaphore(100, loop=uvloop)


@app.route("/check", methods=["POST", "OPTIONS"])
@cross_origin(app, automatic_options=True)
async def post_check(request):
	logger.info("Starting check")
	phq9_url = 'https://raw.githubusercontent.com/ReproNim/schema-standardization' \
			   '/master/activities/PHQ-9/phq9_schema.jsonld'
	jsonobject = request.json
	scoreObj = item_generator(jsonobject, phq9_url)
	if isinstance(scoreObj, dict):
		qualresult, rbin = await qualified(scoreObj)
		if qualresult:
			token, expiration = await get_token(rbin)
			return json({"qualified": 1,
						 "token": token,
						 "expiry": expiration})
	return json({"qualified": 0})


def item_generator(json_input, phq9_url):
	''' recursive iteration through nested json for a specific key '''
	if isinstance(json_input, dict):
		for k, v in json_input.items():
			if k == phq9_url:
				return v
			else:
				return item_generator(v, phq9_url)
	return None


@app.route("/submit", methods=["POST",])
async def post_submit(request):
	token = request.form['token'][0]
	logger.info((token, pending_tokens))
	if token not in pending_tokens:
		return text("Token not valid")
	# add data
	if not os.path.exists(config["upload"]):
		os.makedirs(config["upload"])
	data_file = request.files.get('file')
	file_parameters = {
		'body': data_file.body,
		'name': data_file.name,
		'type': data_file.type,
	}
	f = open(config['upload'] + "/" + 'study-data.zip', "wb")
	f.write(file_parameters['body'])
	print(request.headers['referer'], request.headers['user-agent'])
	# write referer and user-agent info to file
	f.close()

	_, bin = pending_tokens[token]
	current_bins[bin] += 1
	del pending_tokens[token]
	await flush_tokens()
	return json({"status": "accepted"})

if __name__ == "__main__":
	logger.info("Starting backend")
	app.run(host="0.0.0.0", port=8000)
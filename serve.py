import asyncio
from datetime import datetime  
from datetime import timedelta 
import math
import uuid

from sanic import Sanic
from sanic.log import logger
from sanic.response import json, text

import logging
hdlr = logging.FileHandler('/vagrant/db.log')
#formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
#hdlr.setFormatter(formatter)
logger.addHandler(hdlr) 

max_per_bin = 1  # max data required per bin
slop_factor = 1  # allow up to this many tokens
expiry_time = timedelta(minutes=20)  # token expiration delay

current_bins = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
pending_bins = current_bins.copy()
pending_tokens = {}

app = Sanic()


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
    ts = data["total_score"]
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


@app.route("/check", methods=["POST",])
async def post_check(request):
    logger.info("Starting check")
    qualresult, rbin = await qualified(request.json)
    if qualresult:
        token, expiration = await get_token(rbin)
        return json({"qualified": "yes",
                     "token": token,
                     "expiry": expiration})
    return json({"qualified": "no"})


@app.route("/submit", methods=["POST",])
async def post_submit(request):
    token = request.json['token']
    logger.info((token, pending_tokens))
    if token not in pending_tokens:
        return text("Token not valid")
    # add data
    _, bin = pending_tokens[token]
    current_bins[bin] += 1
    del pending_tokens[token]
    await flush_tokens()
    return json({"status": "accepted"})

if __name__ == "__main__":
    logger.info("Starting backend")
    app.run(host="0.0.0.0", port=8000)

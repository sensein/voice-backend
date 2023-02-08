import json
import sys

from sanic import Sanic
from sanic.log import logger
from sanic import response
import requests

app = Sanic("testback")

server = "http://localhost:8000"

@app.route("/")
def main(request):
    logger.debug(request.app.config)
    auth_token = request.app.config['CONFIG']['auth_token']
    submit_code = f"""
<a href="/submit/?auth_token={auth_token}">Submit some data</a>        
"""
    return response.html(f"""
<html>
{request.args}
<br />
{submit_code}
</html>
""")


dummy_response = [
    {
        "@context": "https://raw.githubusercontent.com/ReproNim/reproschema/master/contexts/generic",
        "@type": "reproterms:ResponseActivity",
        "@id": "uuid:a2bfd83a-871c-49c1-afe1-59941187104b",
        "prov:used": [
            "https://raw.githubusercontent.com/ReproNim/reproschema/master/activities/VoiceScreening/items/audio_check",
            "https://raw.githubusercontent.com/sensein/covid19/master/voice/voice_schema",
            "https://raw.githubusercontent.com/sensein/covid19/master/protocol/Covid19_schema"
        ],
        "lang": "en",
        "prov:startedAtTime": "2020-05-02T15:31:26.989Z",
        "prov:endedAtTime": "2020-05-02T15:31:38.424Z",
        "prov:wasAssociatedWith": "https://sensein.github.io/covid19/",
        "prov:generated": "uuid:ef5ec132-b5cc-45d6-9ff3-2f5cbc308226"
    },
    {
        "@context": "https://raw.githubusercontent.com/ReproNim/reproschema/master/contexts/generic",
        "@type": "reproterms:ResponseActivity",
        "@id": "uuid:a2bfd83a-871c-49c1-afe1-59941187104b",
        "prov:used": [
            "https://raw.githubusercontent.com/ReproNim/reproschema/master/activities/VoiceScreening/items/audio_check",
            "https://raw.githubusercontent.com/sensein/covid19/master/voice/voice_schema",
            "https://raw.githubusercontent.com/sensein/covid19/master/protocol/Covid19_schema"
        ],
        "lang": "en",
        "prov:startedAtTime": "2020-05-02T15:31:26.989Z",
        "prov:endedAtTime": "2020-05-02T15:31:38.424Z",
        "prov:wasAssociatedWith": "https://sensein.github.io/covid19/",
        "prov:generated": "uuid:ef5ec132-b5cc-45d6-9ff3-2f5cbc308226"
    },
]


@app.route("/submit")
def submit(request):
    auth_token = request.args["auth_token"][0]
    files = {"file": ('README.md',
                      open('README.md', 'rb'),
                      'text/markdown')}
    data = {"auth_token": auth_token,
            "responses": json.dumps(dummy_response)}
    logger.debug(data)
    req1 = requests.post(f"{server}/submit/", files=files, data=data)
    # submit without files
    req2 = requests.post(f"{server}/submit/", data=data)
    return response.json([req1.json(), req2.json()])


@app.listener('before_server_start')
def before_start(app, loop):
    logger.debug(sys.argv)
    req = requests.get("http://localhost:8000/token",
                       params={"token": sys.argv[1]})
    logger.debug(f"{req.json()}")
    config = {'auth_token': req.json()["auth_token"]}
    logger.info(f"{config}")
    app.config['CONFIG'] = config

if __name__ == "__main__":
    logger.info("Starting test service")
    app.run(host="0.0.0.0", port=3000)

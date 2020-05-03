import sys

from sanic import Sanic
from sanic.log import logger
from sanic import response
import requests

app = Sanic("testback")

client_id = None
server = "http://localhost:8000"
@app.route("/")
async def main(request):
    global client_id
    if client_id is None:
        return html("Unknown client id")
    return response.html(f"""
<html>
<a href="{server}/token/?client_id={client_id}">No participant</a>
<br />
<a href="{server}/token/?client_id={client_id}&participant_id=foo">With participant</a>
<br />
<a href="{server}/token/?client_id={client_id}&participant_id=foo&expiry_minutes=5">With participant + expiry minutes</a>
<br />
{request.args or None}
</html>
""")

if __name__ == "__main__":
    logger.info(sys.argv)
    logger.info("Starting test service")
    req = requests.get("http://localhost:8000/register",
                       params={"token": sys.argv[1],
                               "callback_url": "http://localhost:3000/"})
    logger.info(f"{req.content}")
    client_id = req.json()["client_id"]
    logger.info(f"Received client id: {client_id}")
    app.run(host="0.0.0.0", port=3000)

# voice-backend server

`pip install sanic`



to check:

`python serve.py`

`curl --header "Content-Type: application/json" --request POST --data '{"total_score":25}'  http://localhost:8000/check/`

one can reset internal state with:

`curl http://localhost:8000/reset/`
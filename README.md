## Backend data collection server for SIG projects 

To run install `pip install sanic` into a Python 3.6+ environment

```shell
python serve
```
This will generate a `<token_id>` in the console log that you will need to 
register your clients. Please see the section on local development to test out 
the server locally.

There are 3 types of ids:
1. `token_id`: This is auto generated when the server is launched and is used 
for the register process. This id should not be made public. 
2. `client_id`: This is the identifier returned during the registration process. 
This id can be included in the source code.
3. `auth_token`: This id is generated as part of the handshake mechanism between
the registered client app and the server.

### Usage Flow

1. Register and retrieve a client id. This can be done outside of your client 
app.

```
<server_host_url>/register?token=<token_id>&callback_url=<encoded_callback_url>
```

The above request will return a `<client_id>`

2. Use the `<client_id>` inside your app to retrieve a submission authorization 
token:

```
<server_host_url>/token/?client_id=<client_id>
```
The above request will return an `<auth_token>` and an `<expiry>` time. Your 
data submission will need this token and will have to happen before expiry 
time.

The default expiry time is 90 minutes from the request time. You can change this 
by adding the following parameter `expiry_minutes=15` to your request.

In addition, you can add the parameter `participant_id=<id>` to your request and 
this will be added back to the callback url.

## Local development settings

Replace `<server_host_url>` with `http://localhost:8000`. The registration
process will look like this.

`http://localhost:8000/register?token=<token_id>&callback_url=<encoded_callback_url>`

The production server will not accept any localhost authorizations. To use for 
local development environment set the following environment variable: 
`export DEV8dac6d02a913=1`

There is a basic test script that can be used to test the server:

```
python test_serve.py <token_id>
```
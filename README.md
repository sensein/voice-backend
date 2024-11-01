## Backend data collection server for SIG projects 

To run install `pip install sanic sanic-ext requests` into a Python 3.11+ environment

```shell
python serve
```
This will generate a `<token_id>` in the console log that you will need to 
register your clients. Please see the section on local development to test out 
the server locally.

1. `token_id`: This is auto generated when the server is launched. This id should 
not be made public. It is used to request authorization tokensfrom the server.
2. `auth_token`: This is generated on request. This id can be used to submit data to
the server.

See the `test_serve.py` submit route example to see how to formulate a POST 
request. This version of the server can receive individual messages as a json object or 
an uploaded file.

### Usage Flow

0. Set the environment variable `REPROSCHEMA_BACKEND_BASEDIR` to indicate the directory
where the logs and data will be stored. If not provided, it will default to a 
directory called `reproschema_backend` in the current working directory.
1. Launch server. In production mode, the console log will have a `TOKEN` in the logs 
directory in the `REPROSCHEMA_BACKEND_BASEDIR`. Retrieve this token. 
2. Use the `TOKEN` to retrieve an authorization token for submission.

```
curl <server_host_url>/token/?token=TOKEN
```

The above request will return a JSON response containing `<auth_token>` and an 
`<expiry_time>` time. Your data submission will need this token and will have 
to happen before expiry time.

The default expiry time is 90 minutes from the request time. You can change this 
by adding the following parameter `expiry_minutes=15` to your request.

In addition, you can and should add the parameter `project=<project_name>` to your 
request. This will allow you to submit data to multiple projects. On the server side,
a separate directory will be created for each project.

An example response for a locally running server.

```shell
$ curl 'http://localhost:8000/token?token=440482f593034d489d0b781bd31ccc3d&project=b2ai'
{"auth_token":"b2ai-15055d9b53bf485a8b9be87761dba01c","expires":"20241101T023615Z"}
```

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
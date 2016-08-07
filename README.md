meditations
===========

Initially:

    ./tools/setup.sh
    . virtualenv/bin/activate

Developing:

    ./tools/serve.sh

Deploying:

    ./tools/deploy.py

Running deploy will update the API definition, and lambda functions, roles, and
cloudwatch alarms.

Testing:

    nose2

See also:

http://blog.ryankelly.us/2016/08/07/going-serverless-with-aws-lambda-and-api-gateway.html

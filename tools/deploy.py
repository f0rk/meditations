#!/usr/bin/env python
# Copyright 2016, Ryan Kelly.

from __future__ import absolute_import

import json
import os
import shutil
import subprocess

import botocore.session


EMAIL = "youremail@example.com"


shutil.rmtree("build", ignore_errors=True)
os.makedirs("build")

session = botocore.session.get_session()

# check for our api. if it doesn't exist, create it
apigateway_client = session.create_client("apigateway")

apis = apigateway_client.get_rest_apis()
api = [api for api in apis["items"] if api["name"] == "meditations"]

if not api:

    api = apigateway_client.create_rest_api(name="meditations")

else:

    api = api[0]

# create lambda execution role if it doesn't exist
iam_client = session.create_client("iam")

roles = iam_client.list_roles(PathPrefix="/meditations/lambda/")
meditate_role = [role for role in roles["Roles"] if role["RoleName"] == "meditations_meditate"]

assume_role_policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": [
                    "apigateway.amazonaws.com",
                    "lambda.amazonaws.com",
                ],
            },
            "Action": ["sts:AssumeRole"]
        }
    ]
}

if not meditate_role:

    meditate_role = iam_client.create_role(
        Path="/meditations/lambda/",
        RoleName="meditations_meditate",
        AssumeRolePolicyDocument=json.dumps(assume_role_policy),
    )

else:

    meditate_role = meditate_role[0]

    iam_client.update_assume_role_policy(
        RoleName="meditations_meditate",
        PolicyDocument=json.dumps(assume_role_policy),
    )

# set the role policy
meditations_meditate_policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        }
    ]
}
iam_client.put_role_policy(
    RoleName="meditations_meditate",
    PolicyName="meditations_meditate",
    PolicyDocument=json.dumps(meditations_meditate_policy),
)

# create/update our lambda functions

# build our zip bundle
zipper = subprocess.Popen(
    ["./tools/zip.sh"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
stdout, stderr = zipper.communicate()
if zipper.returncode:
    raise Exception((stdout, stderr))

with open("build/meditate.py.zip", "rb") as zip_fp:
    zip_contents = zip_fp.read()

lambda_client = session.create_client("lambda")

functions = lambda_client.list_functions()

meditate_function = [func for func in functions["Functions"] if func["FunctionName"] == "meditations_meditate"]

if not meditate_function:

    meditate_function = lambda_client.create_function(
        FunctionName="meditations_meditate",
        Runtime="python2.7",
        Role=meditate_role["Arn"],
        Handler="meditate.handler",
        Code={
            "ZipFile": zip_contents,
        }
    )

else:

    meditate_function = meditate_function[0]

    lambda_client.update_function_code(
        FunctionName="meditations_meditate",
        ZipFile=zip_contents, # automatically encoded here
    )

# update the swagger file as necessary
with open("server/swagger.json", "r") as swagger_fp:
    swagger = json.load(swagger_fp)

# set correct host in swagger
swagger["host"] = "{}.execute-api.us-east-1.amazonaws.com".format(api["id"])

# set function location
swagger["paths"]["/"]["post"]["x-amazon-apigateway-integration"]["uri"] = (
    "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/{}/invocations"
    .format(meditate_function["FunctionArn"])
)

print(swagger)

# update api from swagger definition
apigateway_client.put_rest_api(
    restApiId=api["id"],
    mode="overwrite",
    failOnWarnings=True,
    body=json.dumps(swagger),
)

# since I can't figure out how to require an API key from the swagger
# definition, we'll do it manually
meditations_resources = apigateway_client.get_resources(restApiId=api["id"])

main_resource = [res for res in meditations_resources["items"] if res["path"] == "/"][0]

apigateway_client.update_method(
    restApiId=api["id"],
    resourceId=main_resource["id"],
    httpMethod="POST",
    patchOperations=[
        {
            "op": "replace",
            "path": "/apiKeyRequired",
            "value": "true",
        }
    ]
)

# deploy the api
apigateway_client.create_deployment(
    restApiId=api["id"],
    stageName="prod",
)

# setup sns and cloudwatch so we can be notified of errors and billing issues
sns_client = session.create_client("sns")

def create_cloudwatch_topic(Name, email):
    topic = sns_client.create_topic(Name=Name)

    subscription = None
    next_token = None
    while True:

        kwargs = {
            "TopicArn": topic["TopicArn"],
        }

        if next_token is not None:
            kwargs["NextToken"] = next_token

        subscriptions = sns_client.list_subscriptions_by_topic(**kwargs)

        for maybe in subscriptions["Subscriptions"]:
            if maybe["Endpoint"] == email:
                subscription = maybe
                break

        if subscription is not None:
            break

        if "NextToken" in subscriptions:
            next_token = subscriptions["NextToken"]
        else:
            break

    if subscription is None:
        subscription = sns_client.subscribe(
            TopicArn=topic["TopicArn"],
            Protocol="email",
            Endpoint=email,
        )

    return topic

errors_topic = create_cloudwatch_topic("meditations-errors", EMAIL)
billing_topic = create_cloudwatch_topic("meditations-billing", EMAIL)

cloudwatch_client = session.create_client("cloudwatch")
errors_alarm = cloudwatch_client.put_metric_alarm(
    AlarmName="meditations-errors",
    MetricName="Errors",
    ActionsEnabled=True,
    Namespace="AWS/Lambda",
    Statistic="Sum",
    Period=60,
    EvaluationPeriods=1,
    Threshold=1,
    ComparisonOperator="GreaterThanOrEqualToThreshold",
    Dimensions=[
        {
            "Name": "FunctionName",
            "Value": "meditations_meditate",
        },
    ],
    AlarmActions=[
        errors_topic["TopicArn"],
    ],
)

lambda_billing_alarm = cloudwatch_client.put_metric_alarm(
    AlarmName="meditations-billing-lambda",
    MetricName="EstimatedCharges",
    ActionsEnabled=True,
    Namespace="AWS/Lambda",
    Statistic="Maximum",
    Period=86400,
    EvaluationPeriods=1,
    Threshold=0.1,
    ComparisonOperator="GreaterThanOrEqualToThreshold",
    Dimensions=[
        {
            "Name": "Currency",
            "Value": "USD",
        },
    ],
    AlarmActions=[
        billing_topic["TopicArn"],
    ],
)

apigateway_billing_alarm = cloudwatch_client.put_metric_alarm(
    AlarmName="meditations-billing-apigateway",
    MetricName="EstimatedCharges",
    ActionsEnabled=True,
    Namespace="AWS/APIGateway",
    Statistic="Maximum",
    Period=86400,
    EvaluationPeriods=1,
    Threshold=0.5,
    ComparisonOperator="GreaterThanOrEqualToThreshold",
    Dimensions=[
        {
            "Name": "Currency",
            "Value": "USD",
        },
    ],
    AlarmActions=[
        billing_topic["TopicArn"],
    ],
)

# api key
meditations_api_keys = apigateway_client.get_api_keys(
    nameQuery="meditations",
    includeValues=True,
)

meditations_api_key = [ak for ak in meditations_api_keys["items"] if ak["name"] == "meditations"]

if not meditations_api_key:

    meditations_api_key = apigateway_client.create_api_key(
        name="meditations",
        description="ohm",
        enabled=True,
        generateDistinctId=True,
    )

else:

    meditations_api_key = meditations_api_key[0]

print(u"api key: {}".format(meditations_api_key["value"]))

# setup usage plan for meditations
usage_plans = apigateway_client.get_usage_plans()

meditations_usage_plan = [up for up in usage_plans["items"] if up["name"] == "meditations"]

if not meditations_usage_plan:

    meditations_usage_plan = apigateway_client.create_usage_plan(
        name="meditations",
        description="ohm",
        apiStages=[
            {
                "apiId": api["id"],
                "stage": "prod",
            },
        ],
        throttle={
            "burstLimit": 250,
            "rateLimit": 100,
        },
        quota={
            "limit": 10000,
            "period": "DAY",
        }
    )

else:

    meditations_usage_plan = meditations_usage_plan[0]

# and create a usage plan key if one does not exist
usage_plan_keys = apigateway_client.get_usage_plan_keys(
    usagePlanId=meditations_usage_plan["id"],
    nameQuery="meditations",
)

meditations_usage_plan_key = [upk for upk in usage_plan_keys["items"]]

if not meditations_usage_plan_key:

    meditations_usage_plan_key = apigateway_client.create_usage_plan_key(
        usagePlanId=meditations_usage_plan["id"],
        keyId=meditations_api_key["id"],
        keyType="API_KEY",
    )

else:

    meditations_usage_plan_key = meditations_usage_plan_key[0]

print("api deployed to https://{}/prod/".format(swagger["host"]))

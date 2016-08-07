# Copyright 2016, Ryan Kelly.

import logging
import random


logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):

    logger.info(u"received request with id '{}'".format(context.aws_request_id))

    meditations = [
	"off to a regex/",
	"the count of machines abides",
	"you wouldn't fax a bat",
	"HAZARDOUS CHEMICALS + RKELLY",
	"your solution requires a blood eagle",
	"testing is broken because I'm lazy",
	"did u mention banana cognac shower",
    ]

    meditation = random.choice(meditations)

    return {
        "status": "success",
        "meditation": meditation,
    }

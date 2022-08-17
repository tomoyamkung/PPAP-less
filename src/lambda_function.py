import json
import logging


def lambda_handler(event: dict[str, str], context):
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.info(json.dumps(event))

    if "challenge" in event:
        return event.get("challenge")


def echo(arg: str) -> str:
    return arg

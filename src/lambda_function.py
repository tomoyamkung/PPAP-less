import json
import logging
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import boto3


def lambda_handler(event: dict[str, str], context):
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.info(json.dumps(event))

    if "challenge" in event:
        return event.get("challenge")

    if event["Records"][0]["s3"]["object"]["size"] == 0:  # type: ignore
        # PUT されたファイルがゼロバイトの場合は処理終了
        print("ファイルサイズが ゼロ のファイルはアップロードしないでください。")
        return

    object_key: str = urllib.parse.unquote_plus(event["Records"][0]["s3"]["object"]["key"])  # type: ignore
    presigned_url = get_generate_presigned_url(
        event["Records"][0]["s3"]["bucket"]["name"], object_key  # type: ignore
    )
    expiration_datetime: datetime = datetime.fromtimestamp(
        int(presigned_url[-10:]), timezone(timedelta(hours=+9), "JST")
    )
    message: str = json.dumps(
        {
            "FileName": object_key,  # 事前署名 URL 対象ファイル名
            "expiration datetime": expiration_datetime,  # 有効期限（日本時間）
            "URL": presigned_url,  # 事前署名 URL
        },
        cls=CustomJSONEncoder,
    )
    logger.info(message)

    return post_slack(message)


def post_slack(message: str) -> str:
    request = urllib.request.Request(
        os.environ["INCOMING_WEBHOOK_URL"],
        data=json.dumps({"text": message}).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json; charset=UTF-8"},
    )
    with urllib.request.urlopen(request) as response:
        response_body = response.read().decode("utf-8")

    return response_body


def get_expire_setting() -> int:
    # 指定した日数 x 1日の秒数（60 * 60 * 24）
    return int(os.environ["EXPIRE"]) * 60 * 60 * 24


def get_generate_presigned_url(bucket_name: str, object_key: str) -> str:
    access_key_id, secret_access_key = get_credentials()
    s3 = boto3.client(
        "s3",
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
    )
    return s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={
            "Bucket": bucket_name,
            "Key": object_key,
        },
        ExpiresIn=get_expire_setting(),
        HttpMethod="GET",
    )


def get_credentials() -> tuple[str, str]:
    response = boto3.client("secretsmanager").get_secret_value(
        SecretId=os.environ["SECRET"]
    )
    secrets = json.loads(response["SecretString"])
    return (secrets["accessKeyId"], secrets["secretAccessKey"])


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if hasattr(o, "__iter__"):
            return list(o)
        elif isinstance(o, datetime):
            return o.isoformat()
        else:
            return str(o)

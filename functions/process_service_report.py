import json
import os
from datetime import datetime, timezone

import boto3
from botocore.config import Config


endpoint_url = os.environ["FLOCI_ENDPOINT_URL"]
bucket_name = os.environ["REPORTS_BUCKET"]
table_name = os.environ["REPORTS_TABLE"]

s3 = boto3.client(
    "s3",
    endpoint_url=endpoint_url,
    region_name="us-east-1",
    config=Config(s3={"addressing_style": "path"}),
)

dynamodb = boto3.resource(
    "dynamodb",
    endpoint_url=endpoint_url,
    region_name="us-east-1",
)

table = dynamodb.Table(table_name)


def process_report(event):
    """Read a service report from S3 and save the result to DynamoDB."""
    report_id = event.get("report_id")
    key = event.get("key")

    if not report_id or not key:
        raise ValueError("Missing required fields: report_id and key")

    response = s3.get_object(
        Bucket=bucket_name,
        Key=key,
    )

    with response["Body"] as body:
        report = json.loads(body.read())

    if report.get("report_id") != report_id:
        raise ValueError("Event report_id does not match the report")

    item = {
        "report_id": report_id,
        "registration_number": report["registration_number"],
        "vehicle_make": report["vehicle_make"],
        "vehicle_model": report["vehicle_model"],
        "status": "processed",
        "s3_bucket": bucket_name,
        "s3_key": key,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }

    table.put_item(Item=item)

    result = {
        "report_id": report_id,
        "status": "processed",
        "processed_at": item["processed_at"],
    }

    print(json.dumps(result))
    return result


def lambda_handler(event, context):
    """Handle SQS messages or a direct invocation."""
    if "Records" in event:
        results = []

        for record in event["Records"]:
            message = json.loads(record["body"])
            result = process_report(message)
            results.append(result)

        return {
            "processed_count": len(results),
            "results": results,
        }

    return process_report(event)

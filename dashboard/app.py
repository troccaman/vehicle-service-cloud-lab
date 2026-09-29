import os
from datetime import datetime, timezone

import boto3
from botocore.config import Config
from flask import Flask, render_template

app = Flask(__name__)


@app.get("/")
def index():
    reports = []
    error = None

    try:
        dynamodb = boto3.resource(
            "dynamodb",
            endpoint_url=os.environ["FLOCI_ENDPOINT_URL"],
            region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
            config=Config(
                connect_timeout=3,
                read_timeout=5,
                retries={"max_attempts": 1},
            ),
        )
        table = dynamodb.Table(os.environ["REPORTS_TABLE"])
        response = table.scan(ConsistentRead=True)
        reports.extend(response.get("Items", []))

        while response.get("LastEvaluatedKey"):
            response = table.scan(
                ConsistentRead=True,
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            reports.extend(response.get("Items", []))

        reports.sort(
            key=lambda report: report.get("processed_at", ""),
            reverse=True,
        )
    except Exception:
        app.logger.exception("Failed to load service reports")
        reports = []
        error = "Unable to load reports. Please try again shortly."

    return render_template(
        "index.html",
        reports=reports,
        error=error,
        processed_count=sum(
            report.get("status") == "processed" for report in reports
        ),
        vehicle_count=len({
            report["registration_number"]
            for report in reports
            if report.get("registration_number")
        }),
        checked_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    )


import json
import secrets
from datetime import date
from uuid import uuid4

from flask import redirect, request, session, url_for

app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    MAX_CONTENT_LENGTH=64 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)


@app.route("/reports/new", methods=["GET", "POST"])
def new_report():
    error = None
    values = request.form.to_dict() if request.method == "POST" else {}

    if "form_token" not in session:
        session["form_token"] = secrets.token_urlsafe(32)

    if request.method == "POST":
        token = values.get("form_token", "")

        if not secrets.compare_digest(token, session["form_token"]):
            return "The form has expired. Reload the page and try again.", 400

        try:
            fields = {}

            for name in (
                "registration_number",
                "vehicle_make",
                "vehicle_model",
            ):
                value = values.get(name, "").strip()

                if not value or len(value) > 80:
                    raise ValueError(
                        "Registration, make and model are required "
                        "and must each be at most 80 characters."
                    )

                fields[name] = value

            service_date = values.get("service_date", "")
            try:
                date.fromisoformat(service_date)
            except ValueError:
                raise ValueError("Enter a valid service date.")

            try:
                odometer = int(values.get("odometer_km", ""))
            except ValueError:
                raise ValueError("Mileage must be a whole number.")

            if not 0 <= odometer <= 10000000:
                raise ValueError("Mileage must be between 0 and 10,000,000 km.")

            work = values.get("work_performed", "").strip()
            if not work or len(work) > 5000:
                raise ValueError(
                    "Describe the work performed using 1–5,000 characters."
                )

        except ValueError as exc:
            error = str(exc)

        if not error:
            report_id = f"service-{uuid4().hex}"
            bucket = os.environ["REPORTS_BUCKET"]
            key = f"reports/{report_id}.json"

            report = {
                "report_id": report_id,
                **fields,
                "registration_number": fields["registration_number"].upper(),
                "service_date": service_date,
                "odometer_km": odometer,
                "work_performed": [
                    line.strip() for line in work.splitlines() if line.strip()
                ],
            }

            config = Config(
                connect_timeout=3,
                read_timeout=5,
                retries={"total_max_attempts": 1},
                s3={"addressing_style": "path"},
            )
            connection = {
                "endpoint_url": os.environ["FLOCI_ENDPOINT_URL"],
                "region_name": os.environ.get(
                    "AWS_DEFAULT_REGION", "us-east-1"
                ),
                "config": config,
            }

            stage = "save"

            try:
                s3 = boto3.client("s3", **connection)
                s3.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=json.dumps(report, indent=2).encode("utf-8"),
                    ContentType="application/json",
                )

                stage = "queue"
                sqs = boto3.client("sqs", **connection)
                sqs.send_message(
                    QueueUrl=os.environ["REPORTS_QUEUE_URL"],
                    MessageBody=json.dumps({
                        "report_id": report_id,
                        "bucket": bucket,
                        "key": key,
                    }),
                )

            except Exception:
                app.logger.exception(
                    "Report submission failed: report_id=%s stage=%s",
                    report_id,
                    stage,
                )

                if stage == "queue":
                    error = (
                        f"Report {report_id} was saved, but processing could "
                        "not be confirmed. Check the report list before "
                        "submitting again."
                    )
                else:
                    error = (
                        "The report could not be saved with confirmation. "
                        "Please check the application logs."
                    )
            else:
                session.pop("form_token", None)
                return redirect(url_for("index", submitted=report_id))

    return render_template(
        "new-report.html",
        error=error,
        values=values,
        form_token=session["form_token"],
        today=date.today().isoformat(),
    )

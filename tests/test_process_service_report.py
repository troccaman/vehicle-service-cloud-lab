import os
import sys
import json
from pathlib import Path

import pytest

os.environ["FLOCI_ENDPOINT_URL"] = "http://localhost:4566"
os.environ["REPORTS_BUCKET"] = "test-bucket"
os.environ["REPORTS_TABLE"] = "test-table"

sys.path.insert(0, str(Path(__file__).parent.parent / "functions"))

import process_service_report
from process_service_report import process_report


def test_process_report_requires_report_id_and_key():
    event = {
        "report_id": "service-001"
    }

    with pytest.raises(ValueError, match="Missing required fields"):
        process_report(event)

def test_process_report_reads_s3_and_writes_dynamodb(monkeypatch):
    report = {
        "report_id": "service-001",
        "registration_number": "ABC123",
        "vehicle_make": "Volvo",
        "vehicle_model": "V60",
    }

    class FakeBody:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return json.dumps(report).encode()

    class FakeS3:
        def get_object(self, Bucket, Key):
            assert Bucket == "test-bucket"
            assert Key == "reports/service-001.json"

            return {
                "Body": FakeBody()
            }

    saved_items = []

    class FakeTable:
        def put_item(self, Item):
            saved_items.append(Item)

    monkeypatch.setattr(process_service_report, "s3", FakeS3())
    monkeypatch.setattr(process_service_report, "table", FakeTable())

    event = {
        "report_id": "service-001",
        "key": "reports/service-001.json",
    }

    result = process_service_report.process_report(event)

    assert result["report_id"] == "service-001"
    assert result["status"] == "processed"

    assert len(saved_items) == 1
    assert saved_items[0]["registration_number"] == "ABC123"
    assert saved_items[0]["vehicle_make"] == "Volvo"
    assert saved_items[0]["vehicle_model"] == "V60"
    assert saved_items[0]["status"] == "processed"
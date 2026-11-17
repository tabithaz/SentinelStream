import json
import unittest

from fastapi.testclient import TestClient

from app.main import LOGGER, app


class AccessLoggingTests(unittest.TestCase):
    def test_logs_route_template_without_event_id(self):
        with TestClient(app) as client, self.assertLogs(LOGGER, "INFO") as captured:
            response = client.get("/events/id/" + "a" * 64)

        self.assertEqual(response.status_code, 404)
        payload = json.loads(captured.records[-1].getMessage())
        self.assertEqual(payload["path"], "/events/id/{event_id}")

    def test_logs_unmatched_without_request_path(self):
        with TestClient(app) as client, self.assertLogs(LOGGER, "INFO") as captured:
            response = client.get("/unknown/private-identifier")

        self.assertEqual(response.status_code, 404)
        payload = json.loads(captured.records[-1].getMessage())
        self.assertEqual(payload["path"], "unmatched")

"""Router behaviour and consistency between routes.py and the API Gateway definition."""

from __future__ import annotations

import json
import unittest
from unittest import mock

from helpers import BACKEND, AwsTestCase, handler

import routes


def gateway_routes() -> dict[tuple[str, str], str]:
    resources = json.loads((BACKEND / "deployment_resources.json").read_text())["${api_gateway_name}"]["resources"]
    return {
        (method, path): spec["authorization_type"]
        for path, methods in resources.items()
        for method, spec in methods.items()
        if method != "enable_cors"
    }


class ApiContractTest(unittest.TestCase):
    def test_every_gateway_route_has_a_handler_and_vice_versa(self) -> None:
        handled = {(method, template) for method, template, _, _ in routes.ROUTES}
        self.assertEqual(set(gateway_routes()), handled)

    def test_admin_mutations_require_the_cognito_authorizer(self) -> None:
        auth = gateway_routes()
        for route in [
            ("POST", "/dishes"),
            ("POST", "/locations"),
            ("POST", "/tables"),
            ("POST", "/waiters"),
            ("DELETE", "/waiters"),
        ]:
            self.assertEqual("cognito_authorizer", auth[route], route)

    def test_public_routes_stay_public(self) -> None:
        auth = gateway_routes()
        for route in [
            ("POST", "/signin"),
            ("POST", "/register"),
            ("GET", "/guest/invites/{token}"),
            ("POST", "/guest/sessions"),
            ("POST", "/feedback"),
        ]:
            self.assertEqual("NONE", auth[route], route)


class RouterTest(AwsTestCase):
    def test_cors_preflight(self) -> None:
        response = handler({"httpMethod": "OPTIONS", "path": "/locations", "headers": {}})
        self.assertEqual(200, response["statusCode"])
        self.assertEqual("*", response["headers"]["Access-Control-Allow-Origin"])
        self.assertIn("PATCH", response["headers"]["Access-Control-Allow-Methods"])

    def test_unknown_route(self) -> None:
        self.assertEqual({"error": "Not Found", "message": "Not Found"}, self.error(404, "GET", "/nope"))

    def test_stage_prefix_and_trailing_slash(self) -> None:
        self.assertEqual([], self.ok("GET", "/develop/locations/"))

    def test_unexpected_errors_become_500(self) -> None:
        with mock.patch("services.locations.list_locations", side_effect=RuntimeError("boom")):
            body = self.error(500, "GET", "/locations")
        self.assertEqual("Internal Server Error", body["error"])

    def test_invalid_json_body(self) -> None:
        status, body = self.call("POST", "/signin")
        self.assertEqual((400, "Request body is empty"), (status, body["error"]))
        response = handler({"httpMethod": "POST", "path": "/signin", "headers": {}, "body": "{not json"})
        self.assertEqual(400, response["statusCode"])

    def test_malformed_binary_body_is_a_client_error(self) -> None:
        for body in ("!not-base64", "/w=="):
            response = handler(
                {"httpMethod": "POST", "path": "/signin", "headers": {}, "body": body, "isBase64Encoded": True}
            )
            self.assertEqual(400, response["statusCode"])


if __name__ == "__main__":
    unittest.main()

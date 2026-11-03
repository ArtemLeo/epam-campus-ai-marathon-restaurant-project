"""Cloud workflow safety checks with fake AWS/Terraform; never contact a cloud account."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import cloud


class CloudWorkflowTest(unittest.TestCase):
    def test_binary_cors_only_changes_options_and_publishes_stage(self) -> None:
        gateway = Mock()
        gateway.get_paginator.return_value.paginate.return_value = [
            {
                "items": [
                    {"id": "root", "resourceMethods": {"GET": {}}},
                    {"id": "reports", "resourceMethods": {"GET": {}, "OPTIONS": {}}},
                ]
            }
        ]
        cloud.configure_binary_cors(gateway, "restaurant-api")
        target = {"restApiId": "restaurant-api", "resourceId": "reports", "httpMethod": "OPTIONS"}
        patch = [{"op": "replace", "path": "/contentHandling", "value": "CONVERT_TO_TEXT"}]
        gateway.update_integration.assert_called_once_with(**target, patchOperations=patch)
        gateway.update_integration_response.assert_called_once_with(**target, statusCode="200", patchOperations=patch)
        gateway.create_deployment.assert_called_once_with(restApiId="restaurant-api", stageName="develop")

    def test_destroy_refusal_precedes_every_mutation(self) -> None:
        with (
            patch.object(cloud, "config", return_value={"account": "123456789012"}),
            patch.object(cloud, "outputs", return_value={}),
            patch("builtins.input", return_value="no"),
            patch.object(cloud, "syndicate") as syndicate,
            patch.object(cloud, "context") as context,
            patch.object(cloud, "tf") as terraform,
        ):
            with self.assertRaisesRegex(SystemExit, "No resources were changed"):
                cloud.destroy()
            syndicate.assert_not_called()
            context.assert_not_called()
            terraform.assert_not_called()

    def test_destroy_only_targets_buckets_from_terraform_and_cleans_both_owners(self) -> None:
        events = []
        session = Mock()
        bucket = session.resource.return_value.Bucket.return_value
        bucket.object_versions.delete.side_effect = lambda: events.append("objects")
        out = {
            "s3_frontend_bucket_name": "frontend",
            "s3_images_bucket_name": "images",
            "s3_profile_images_bucket_name": "profiles",
        }
        saved = {"account": "123456789012", "state_bucket": "state", "artifacts_bucket": "artifacts"}
        with (
            patch.object(cloud, "config", return_value=saved),
            patch.object(cloud, "outputs", return_value=out),
            patch("builtins.input", return_value="DELETE 123456789012"),
            patch.object(cloud, "context", return_value=(session, saved["account"], "eu-north-1")),
            patch.object(cloud, "syndicate", side_effect=lambda command: events.append(command)),
            patch.object(cloud, "tf", side_effect=lambda *args: events.append(args[0])),
        ):
            cloud.destroy()
        self.assertEqual(["clean", "objects", "objects", "objects", "destroy"], events)
        self.assertEqual(
            ["frontend", "images", "profiles"],
            [call.args[0] for call in session.resource.return_value.Bucket.call_args_list],
        )

    def test_configuration_uses_selected_account_and_preserves_foreign_state(self) -> None:
        with tempfile.TemporaryDirectory(prefix="restaurant-cloud-test-") as directory:
            root = Path(directory)
            backend = root / "backend"
            tf = root / "terraform"
            generated = backend / "syndicate" / ".generated"
            generated.mkdir(parents=True)
            tf.mkdir()
            template = (Path(__file__).resolve().parents[1] / "syndicate" / "syndicate_aliases.yml").read_text()
            (backend / "syndicate" / "syndicate_aliases.yml").write_text(template)
            with (
                patch.object(cloud, "BACKEND", backend),
                patch.object(cloud, "TF", tf),
                patch.object(cloud, "GENERATED", generated),
                patch.object(cloud, "context", return_value=(Mock(), "123456789012", "eu-west-1")),
            ):
                cloud.configure()
                config = json.loads((generated / "syndicate.yml").read_text())
                self.assertEqual("123456789012", config["account_id"])
                self.assertEqual(str(backend), config["project_path"])
                self.assertIn("eu-west-1", (tf / "backend.local.hcl").read_text())
                previous = (generated / "context.json").read_text()
                with patch.object(cloud, "context", return_value=(Mock(), "999999999999", "eu-west-1")):
                    with self.assertRaisesRegex(SystemExit, "another account"):
                        cloud.configure()
                    with self.assertRaisesRegex(SystemExit, "differs"):
                        cloud.config()
                self.assertEqual(previous, (generated / "context.json").read_text())


if __name__ == "__main__":
    unittest.main()

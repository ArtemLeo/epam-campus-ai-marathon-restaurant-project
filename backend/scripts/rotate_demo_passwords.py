#!/usr/bin/env python3
"""Rotate passwords for all demo Cognito users.

Usage:
    DEMO_PASSWORD="NewSecure#2026" python3 backend/scripts/rotate_demo_passwords.py
"""

from __future__ import annotations

import os
import sys

import boto3

DEMO_EMAILS = [
    "admin@example.com",
    "testowner@example.com",
    "customer@example.com",
    "guest@example.com",
    "waiter.rustaveli@example.com",
    "waiter.rustaveli2@example.com",
    "waiter.abashidze@example.com",
    "waiter.baratashvili@example.com",
    "testuser2026@gmail.com",
]


def main() -> None:
    password = os.environ.get("DEMO_PASSWORD", "")
    if not password:
        print("Set DEMO_PASSWORD environment variable.", file=sys.stderr)
        sys.exit(1)

    region = os.environ.get("AWS_REGION", "eu-north-1")
    pool_id = os.environ.get("COGNITO_USER_POOL_ID", "eu-north-1_K1wp82SCa")

    cognito = boto3.client("cognito-idp", region_name=region)

    for email in DEMO_EMAILS:
        try:
            cognito.admin_set_user_password(UserPoolId=pool_id, Username=email, Password=password, Permanent=True)
            print(f"  ✓ {email}")
        except cognito.exceptions.UserNotFoundException:
            print(f"  – {email} (not found, skipped)")
        except Exception as exc:
            print(f"  ✗ {email}: {exc}")

    print("Done. All demo users now use the new DEMO_PASSWORD.")


if __name__ == "__main__":
    main()

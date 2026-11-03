"""Registration, sign-in, profile and user search."""

from __future__ import annotations

import base64
import unittest

from helpers import PASSWORD, AwsTestCase

PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32).decode()


class UsersTest(AwsTestCase):
    def register(self, **overrides):
        body = {
            "firstName": "John",
            "lastName": "Doe",
            "email": "John@Mail.com",
            "password": PASSWORD,
            "confirmPassword": PASSWORD,
            **overrides,
        }
        return self.call("POST", "/register", body)

    def test_registration_requires_email_confirmation(self) -> None:
        status, body = self.register()
        self.assertEqual(200, status)
        self.assertTrue(body["confirmationRequired"])
        self.assertEqual(
            "UNCONFIRMED", self.cognito.admin_get_user(UserPoolId=self.pool_id, Username="john@mail.com")["UserStatus"]
        )
        pending = self.error(403, "POST", "/signin", {"email": "john@mail.com", "password": PASSWORD})
        self.assertEqual("ConfirmationRequired", pending["errorCode"])
        self.ok("POST", "/confirm-registration", {"email": "john@mail.com", "code": "123456"})
        user = self.cognito.admin_get_user(UserPoolId=self.pool_id, Username="john@mail.com")
        self.assertEqual("CONFIRMED", user["UserStatus"])
        groups = self.cognito.admin_list_groups_for_user(UserPoolId=self.pool_id, Username="john@mail.com")["Groups"]
        self.assertEqual(["Customer"], [g["GroupName"] for g in groups])
        self.assertEqual(409, self.register()[0])

    def test_register_validation(self) -> None:
        cases = {
            "firstName": ("J", "First name must be between 2 and 50 characters long."),
            "lastName": ("D0e", "Last name can only contain letters, spaces, hyphens, and apostrophes."),
            "email": (
                "not-an-email",
                "Invalid email address. Please ensure it follows the format: username@domain.com",
            ),
            "confirmPassword": ("Other1234!", "Passwords do not match."),
        }
        for field, (value, message) in cases.items():
            with self.subTest(field=field):
                status, body = self.register(**{field: value})
                self.assertEqual((400, message), (status, body["error"]))

    def test_sign_in(self) -> None:
        self.register()
        self.ok("POST", "/confirm-registration", {"email": "john@mail.com", "code": "123456"})
        tokens = self.ok("POST", "/signin", {"email": "john@mail.com", "password": PASSWORD})
        self.assertEqual({"message", "idToken", "accessToken"}, set(tokens))
        status, body = self.call("POST", "/signin", {"email": "john@mail.com", "password": "Wrong123!"})
        self.assertEqual((401, "Invalid email or password"), (status, body["error"]))

    def test_password_recovery_changes_the_password(self) -> None:
        self.create_user("reset@mail.com")
        self.cognito.admin_update_user_attributes(
            UserPoolId=self.pool_id,
            Username="reset@mail.com",
            UserAttributes=[{"Name": "email_verified", "Value": "true"}],
        )
        existing = self.ok("POST", "/forgot-password", {"email": "reset@mail.com"})
        missing = self.ok("POST", "/forgot-password", {"email": "missing@mail.com"})
        self.assertEqual(existing, missing)
        self.ok("POST", "/reset-password", {"email": "reset@mail.com", "code": "123456", "newPassword": "NewPassw0rd!"})
        self.error(401, "POST", "/signin", {"email": "reset@mail.com", "password": PASSWORD})
        self.ok("POST", "/signin", {"email": "reset@mail.com", "password": "NewPassw0rd!"})

    def test_weak_password_and_whitespace_only_names_are_rejected(self) -> None:
        self.assertEqual(400, self.register(password="lowercase", confirmPassword="lowercase")[0])
        self.assertEqual(400, self.register(firstName=" A ")[0])
        self.assertEqual(
            200, self.register(firstName="Олена", lastName="Ковальчук", email="olena+demo@example.technology")[0]
        )

    def test_me_returns_profile_and_highest_role(self) -> None:
        admin = self.create_user("boss@mail.com", "Anna", "Boss", groups=("Customer", "Admin"))
        me = self.ok("GET", "/me", user=admin)
        self.assertEqual(
            {"id": admin["id"], "firstName": "Anna", "lastName": "Boss", "email": "boss@mail.com", "role": "Admin"}, me
        )
        self.error(401, "GET", "/me")

    def test_update_profile_and_change_password(self) -> None:
        user = self.create_user("john@mail.com")
        self.ok("PUT", "/me", {"firstName": "Johnny", "lastName": "Doe-Smith"}, user=user)
        self.assertEqual("Johnny", self.ok("GET", "/me", user=user)["firstName"])
        self.error(400, "PUT", "/me", {"firstName": "J", "lastName": "Doe"}, user=user)

        token = self.ok("POST", "/signin", {"email": "john@mail.com", "password": PASSWORD})["accessToken"]
        self.ok(
            "PUT",
            "/me/change-password",
            {"oldPassword": PASSWORD, "newPassword": "N3wPassw0rd!", "accessToken": token},
            user=user,
        )
        self.ok("POST", "/signin", {"email": "john@mail.com", "password": "N3wPassw0rd!"})

    def test_user_search_is_for_waiters(self) -> None:
        customer = self.create_user("john@mail.com", "John", "Doe")
        self.create_user("jane@mail.com", "Jane", "Roe")
        waiter = self.create_user("w@mail.com", "Walt", "Waiter", groups=("Waiter",))
        self.error(403, "GET", "/users", user=customer, query={"fullName": "Jo"})
        found = self.ok("GET", "/users", user=waiter, query={"fullName": "Jo Doe"})
        self.assertEqual(["john@mail.com"], [u["email"] for u in found])
        self.error(400, "GET", "/users", user=waiter, query={"fullName": " "})

    def test_user_name(self) -> None:
        user = self.create_user("john@mail.com", "John", "Doe")
        self.assertEqual({"name": "John Doe"}, self.ok("GET", f"/users/{user['id']}/name", user=user))
        self.assertEqual({"name": "Anonymous User"}, self.ok("GET", "/users/unknown/name", user=user))

    def test_profile_image_upload_and_presigned_url(self) -> None:
        user = self.create_user("john@mail.com")
        self.assertEqual("Profile image is not uploaded so far.", self.ok("GET", f"/users/{user['id']}/profile-image"))
        self.assertEqual(
            "Photo was uploaded successfully!",
            self.ok("PUT", "/me/profile-image", {"base64Image": f"data:image/png;base64,{PNG}"}, user=user),
        )
        url = self.ok("GET", f"/users/{user['id']}/profile-image")["presignedUrl"]
        self.assertIn("profile-img/user_", url)
        # Uploading the same picture again just returns its URL.
        self.assertIn("presignedUrl", self.ok("PUT", "/me/profile-image", {"base64Image": PNG}, user=user))
        self.error(
            400, "PUT", "/me/profile-image", {"base64Image": base64.b64encode(b"not an image").decode()}, user=user
        )


if __name__ == "__main__":
    unittest.main()

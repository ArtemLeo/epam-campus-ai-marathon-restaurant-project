"""Registration, sign-in and profile operations backed by Amazon Cognito."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from core import auth, aws, config
from core.auth import Caller
from core.errors import ApiError, BadRequest, Conflict, NotFound, Unauthorized
from core.validation import validate_email, validate_name, validate_password, validate_passwords
from repositories import people
from services import images

logger = logging.getLogger(__name__)

Item = dict[str, Any]


def register(first_name: Any, last_name: Any, email: Any, password: Any, confirm_password: Any) -> Item:
    first_name = validate_name(first_name, "First name")
    last_name = validate_name(last_name, "Last name")
    email = validate_email(email).strip().lower()
    validate_passwords(password, confirm_password)

    client = aws.cognito()
    try:
        client.sign_up(
            ClientId=config.user_pool_client_id(),
            Username=email,
            Password=password,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "given_name", "Value": first_name},
                {"Name": "family_name", "Value": last_name},
            ],
        )
    except client.exceptions.UsernameExistsException as exc:
        raise Conflict("A user with this email address already exists.") from exc
    except (client.exceptions.InvalidPasswordException, client.exceptions.InvalidParameterException) as exc:
        raise BadRequest(exc.response["Error"]["Message"]) from exc

    return {"message": "Check your email for the confirmation code.", "confirmationRequired": True}


def confirm_registration(email: Any, code: Any) -> None:
    email = validate_email(email).strip().lower()
    if not isinstance(code, str) or not code.strip():
        raise BadRequest("Enter the confirmation code from your email.")
    client = aws.cognito()
    try:
        client.confirm_sign_up(ClientId=config.user_pool_client_id(), Username=email, ConfirmationCode=code.strip())
    except (
        client.exceptions.CodeMismatchException,
        client.exceptions.ExpiredCodeException,
        client.exceptions.UserNotFoundException,
    ) as exc:
        raise BadRequest("The confirmation code is invalid or expired.") from exc
    except client.exceptions.NotAuthorizedException as exc:
        raise BadRequest("This account is already confirmed. You can sign in.") from exc
    people.ensure_group(auth.CUSTOMER)
    people.add_to_group(email, auth.CUSTOMER)


def resend_confirmation(email: Any) -> Item:
    email = validate_email(email).strip().lower()
    client = aws.cognito()
    try:
        client.resend_confirmation_code(ClientId=config.user_pool_client_id(), Username=email)
    except client.exceptions.UserNotFoundException:
        pass
    except client.exceptions.LimitExceededException as exc:
        raise ApiError("Too many attempts. Please try again later.", status=429) from exc
    return {"message": "If this account needs confirmation, a new code has been sent."}


def forgot_password(email: Any) -> Item:
    email = validate_email(email).strip().lower()
    client = aws.cognito()
    try:
        client.forgot_password(ClientId=config.user_pool_client_id(), Username=email)
    except (client.exceptions.UserNotFoundException, client.exceptions.InvalidParameterException):
        pass
    except client.exceptions.LimitExceededException as exc:
        raise ApiError("Too many attempts. Please try again later.", status=429) from exc
    return {"message": "If an account with a verified email exists, a reset code has been sent."}


def reset_password(email: Any, code: Any, new_password: Any) -> None:
    email = validate_email(email).strip().lower()
    validate_passwords(new_password, new_password)
    if not isinstance(code, str) or not code.strip():
        raise BadRequest("Enter the reset code from your email.")
    client = aws.cognito()
    try:
        client.confirm_forgot_password(
            ClientId=config.user_pool_client_id(), Username=email, ConfirmationCode=code.strip(), Password=new_password
        )
    except (
        client.exceptions.CodeMismatchException,
        client.exceptions.ExpiredCodeException,
        client.exceptions.UserNotFoundException,
    ) as exc:
        raise BadRequest("The reset code is invalid or expired.") from exc
    except (client.exceptions.InvalidPasswordException, client.exceptions.InvalidParameterException) as exc:
        raise BadRequest(exc.response["Error"]["Message"]) from exc
    except client.exceptions.LimitExceededException as exc:
        raise ApiError("Too many attempts. Please try again later.", status=429) from exc


def sign_in(email: Any, password: Any) -> Item:
    email = validate_email(email).strip().lower()
    validate_password(password)
    client = aws.cognito()
    try:
        result = client.initiate_auth(
            ClientId=config.user_pool_client_id(),
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": email, "PASSWORD": password},
        )["AuthenticationResult"]
    except client.exceptions.UserNotConfirmedException as exc:
        raise ApiError(
            "Please confirm your email before signing in.", status=403, error_code="ConfirmationRequired"
        ) from exc
    except (
        client.exceptions.NotAuthorizedException,
        client.exceptions.UserNotFoundException,
    ) as exc:
        raise Unauthorized("Invalid email or password") from exc
    return {"message": "Sign in successful", "idToken": result["IdToken"], "accessToken": result["AccessToken"]}


def _username(caller: Caller) -> str:
    username = caller.username or caller.email
    if not username:
        raise Unauthorized("User is not authenticated.")
    return username


def current_user(caller: Caller) -> Item:
    username = _username(caller)
    client = aws.cognito()
    try:
        user = client.admin_get_user(UserPoolId=config.user_pool_id(), Username=username)
    except client.exceptions.UserNotFoundException as exc:
        raise Unauthorized("User is not authenticated.") from exc
    attrs = people.attributes(user)
    return {
        "id": caller.user_id,
        "firstName": attrs.get("given_name", "Unknown"),
        "lastName": attrs.get("family_name", "User"),
        "email": attrs.get("email", "no_email"),
        "role": auth.primary_role(tuple(people.groups_of(username))),
    }


def update_profile(caller: Caller, first_name: Any, last_name: Any) -> None:
    first_name = validate_name(first_name, "First name")
    last_name = validate_name(last_name, "Last name")
    people.update_attributes(_username(caller), {"given_name": first_name, "family_name": last_name})


def change_password(old_password: Any, new_password: Any, access_token: Any) -> None:
    validate_password(old_password)
    validate_passwords(new_password, new_password)
    if not isinstance(access_token, str) or not access_token:
        raise BadRequest("Access token is required.")
    client = aws.cognito()
    try:
        client.change_password(AccessToken=access_token, PreviousPassword=old_password, ProposedPassword=new_password)
    except client.exceptions.NotAuthorizedException as exc:
        raise BadRequest("The old password is incorrect or the session has expired.") from exc
    except (client.exceptions.InvalidPasswordException, client.exceptions.InvalidParameterException) as exc:
        raise BadRequest(exc.response["Error"]["Message"]) from exc
    except client.exceptions.LimitExceededException as exc:
        raise ApiError("Too many attempts. Please try again later.", status=429) from exc


def search_users(full_name: Any) -> list[Item]:
    """Customers whose first name starts with the first word and last name equals the second (waiter search)."""
    if not isinstance(full_name, str) or not full_name.strip():
        raise BadRequest("Missing or empty 'fullName' query parameter.")
    names = full_name.split()
    first = validate_name(names[0], "First name")
    last = validate_name(names[1], "Last name") if len(names) > 1 else ""
    results = []
    for user in people.users_by_given_name_prefix(first):
        attrs = people.attributes(user)
        if last and attrs.get("family_name", "").lower() != last.lower():
            continue
        results.append(
            {
                "id": attrs.get("sub", ""),
                "firstName": attrs.get("given_name", "Unknown"),
                "lastName": attrs.get("family_name", "User"),
                "email": attrs.get("email", "no_email"),
                "role": auth.CUSTOMER,
            }
        )
    return results


def user_name(user_id: str) -> str:
    return people.full_name(user_id) or "Anonymous User"


def profile_image_url(user_id: str) -> str | None:
    record = people.get_profile_image(user_id)
    if not record or not record.get("imageKey"):
        return None
    return images.presigned_url(config.profile_images_bucket(), record["imageKey"])


def upload_profile_image(caller: Caller, image_base64: Any) -> str | None:
    """Store the caller's photo; returns the existing URL when the same image is uploaded again."""
    image = images.decode_base64_image(image_base64)
    images.content_type(image)
    bucket = config.profile_images_bucket()
    record = people.get_profile_image(caller.user_id)
    old_key = record.get("imageKey") if record else None
    if old_key:
        existing = images.download(bucket, old_key)
        if existing is not None and images.same_image(image, existing):
            return images.presigned_url(bucket, old_key)
    key = images.upload(
        image, bucket, images.PROFILE_FOLDER, f"user_{caller.user_id}_{hashlib.sha256(image).hexdigest()[:16]}"
    )
    people.save_profile_image(caller.user_id, key)
    if old_key and old_key != key:
        try:
            images.delete(bucket, old_key)
        except Exception:
            logger.warning("Could not remove the previous profile photo", exc_info=True)
    return None


def require_user_id_by_email(email: str) -> str:
    user = people.user_by_email(email)
    user_id = people.attributes(user).get("sub")
    if not user_id:
        raise NotFound(f"User with email {email} is not registered")
    return user_id

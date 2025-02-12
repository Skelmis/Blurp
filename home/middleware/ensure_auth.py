from __future__ import annotations

import os

import commons
from dotenv import load_dotenv
from litestar import Request
from litestar.connection import ASGIConnection
from litestar.exceptions import NotAuthorizedException
from litestar.middleware import (
    AbstractAuthenticationMiddleware,
    AuthenticationResult,
)
from piccolo.apps.user.tables import BaseUser
from piccolo_api.session_auth.tables import SessionsBase

from home.exception_handlers import RedirectForAuth
from home.util.flash import alert

load_dotenv()
REQUIRE_AUTH: bool = commons.value_to_bool(os.environ.get("REQUIRE_AUTH"))


class EnsureAuth(AbstractAuthenticationMiddleware):
    session_table = SessionsBase
    auth_table = BaseUser
    cookie_name = "id"
    admin_only = False
    superuser_only = False
    active_only = True
    increase_expiry = None
    requires_auth = REQUIRE_AUTH

    @classmethod
    async def get_user_from_connection(
        cls,
        connection: ASGIConnection | Request,
        possible_redirect: str = "/",
        *,
        fail_on_not_set: bool = True,
    ) -> BaseUser | None:
        token = connection.cookies.get(cls.cookie_name, None)
        if not token:
            if fail_on_not_set:
                alert(connection, "Please authenticate to view this resource")
                raise RedirectForAuth(possible_redirect)

            return None

        user_id = await cls.session_table.get_user_id(
            token, increase_expiry=cls.increase_expiry
        )

        if not user_id:
            alert(connection, "Please authenticate to view this resource")
            raise RedirectForAuth(possible_redirect)

        return (
            await cls.auth_table.objects()
            .where(cls.auth_table._meta.primary_key == user_id)
            .first()
            .run()
        )

    async def authenticate_request(
        self, connection: ASGIConnection
    ) -> AuthenticationResult:
        if not self.requires_auth:
            return AuthenticationResult(user=None, auth=None)

        possible_redirect = (
            f"{connection.url.path}?{connection.url.query}"
            if connection.url.query
            else connection.url.path
        )
        piccolo_user = await self.get_user_from_connection(
            connection, possible_redirect
        )

        if not piccolo_user:
            # Used to say "That user doesn't exist anymore"
            raise NotAuthorizedException("That user doesn't exist")

        if self.admin_only and not piccolo_user.admin:
            raise NotAuthorizedException("Admin users only")

        if self.superuser_only and not piccolo_user.superuser:
            raise NotAuthorizedException("Superusers only")

        if self.active_only and not piccolo_user.active:
            raise NotAuthorizedException("Active users only")

        return AuthenticationResult(user=piccolo_user, auth=None)

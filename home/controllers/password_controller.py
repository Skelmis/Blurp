import hmac
from typing import Any, cast

from commons.hibp import has_password_been_pwned
from litestar import Controller, get, MediaType, Request, post
from litestar.exceptions import SerializationException
from litestar.response import Template, Redirect
from piccolo.apps.user.tables import BaseUser

from home.controllers import LogoutController
from home.middleware import EnsureAuth
from home.util import get_csp
from home.util.flash import alert


class PasswordController(Controller):
    path = "/passwords"

    @get(include_in_schema=False, name="forgot_password", path="/forgot")
    async def forgot_password_get(self, request: Request) -> Template:
        alert(
            request,
            "This functionality hasn't been implemented yet. "
            "Reach out to your administrator.",
            level="info",
        )
        csp, nonce = get_csp()
        return Template(
            "auth/forgot_password.jinja",
            context={
                "csp_nonce": nonce,
            },
            media_type=MediaType.HTML,
            headers={"content-security-policy": csp},
        )

    @post(tags=["Auth"], path="/forgot")
    async def forgot_password_post(self, request: Request) -> Redirect:
        return Redirect("/passwords/forgot")

    @get(
        include_in_schema=False,
        name="change_password",
        path="/change",
        middleware=[EnsureAuth],
    )
    async def change_password_get(self) -> Template:
        csp, nonce = get_csp()
        return Template(
            "auth/change_password.jinja",
            context={
                "csp_nonce": nonce,
            },
            media_type=MediaType.HTML,
            headers={"content-security-policy": csp},
        )

    @post(tags=["Auth"], path="/change", middleware=[EnsureAuth])
    async def change_password_post(self, request: Request) -> Template | Redirect:
        # Some middleware (for example CSRF) has already awaited the request
        # body, and adds it to the request.
        body: Any = request.scope.get("form")

        if not body:
            try:
                body = await request.json()
            except SerializationException:
                body = await request.form()

        current_password = body.get("current_password")
        new_password = body.get("new_password")
        new_password_again = body.get("new_password_again")

        if (
            current_password is None
            or new_password is None
            or new_password_again is None
        ):
            alert(request, "Please fill in all form fields.", level="error")
            return Redirect("/passwords/change")

        if not hmac.compare_digest(new_password, new_password_again):
            alert(request, "New password fields did not match.", level="error")
            return Redirect("/passwords/change")

        user = cast(BaseUser, request.user)
        algorithm, iterations_, salt, hashed = BaseUser.split_stored_password(
            user.password
        )
        iterations = int(iterations_)
        if BaseUser.hash_password(current_password, salt, iterations) != user.password:
            alert(request, "Your current password was wrong.", level="error")
            return Redirect("/passwords/change")

        if await has_password_been_pwned(new_password):
            alert(
                request,
                "Your new password appears in breach databases, "
                "please pick a unique password.",
                level="error",
            )
            return Redirect("/passwords/change")

        await user.update_password(user.id, new_password)
        alert(
            request,
            "Successfully changed password, please reauthenticate.",
            level="success",
        )
        return await LogoutController.logout_current_user(request)

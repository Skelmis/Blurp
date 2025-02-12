import os
import typing as t
import warnings
from datetime import timedelta, datetime

from commons import value_to_bool
from commons.hibp import has_password_been_pwned
from litestar import Controller, get, Request, post, MediaType
from litestar.exceptions import SerializationException
from litestar.response import Template, Redirect
from piccolo.apps.user.tables import BaseUser
from piccolo_api.session_auth.tables import SessionsBase
from piccolo_api.shared.auth.styles import Styles
from starlette.exceptions import HTTPException

from home.util import get_csp
from home.util.flash import alert


# Taken from the underlying Piccolo class and modified to work with Litestar
# noinspection PyMethodMayBeStatic
class LoginController(Controller):
    path = "/b/login"
    _auth_table = BaseUser
    _session_table = SessionsBase
    _session_expiry = timedelta(hours=6)
    _max_session_expiry = timedelta(days=3)
    _redirect_to = "/"
    _production = not value_to_bool(os.environ.get("DEBUG"))
    _cookie_name = "id"
    _hooks = None
    _captcha = None
    _styles = Styles()

    def _render_template(self, request: Request, status_code=200) -> Template:
        # If CSRF middleware is present, we have to include a form field with
        # the CSRF token. It only works if CSRFMiddleware has
        # allow_form_param=True, otherwise it only looks for the token in the
        # header.
        csp, nonce = get_csp()
        csrftoken = request.scope.get("csrftoken")
        csrf_cookie_name = request.scope.get("csrf_cookie_name")
        return Template(
            "auth/login.jinja",
            context={
                "csrftoken": csrftoken,
                "csrf_cookie_name": csrf_cookie_name,
                "request": request,
                "captcha": self._captcha,
                "styles": self._styles,
                "csp_nonce": nonce,
                "active": "vulnerabilities",
            },
            status_code=status_code,
            media_type=MediaType.HTML,
            headers={"content-security-policy": csp},
        )

    def _get_error_response(self, request, error: str) -> Redirect:
        alert(request, error, level="error")
        return Redirect("/login")

    @get(include_in_schema=False, name="login")
    async def get(self, request: Request) -> Template:
        return self._render_template(request)

    @post(tags=["Auth"])
    async def post(
        self, request: Request, next_route: str = "/"
    ) -> Template | Redirect:
        # Some middleware (for example CSRF) has already awaited the request
        # body, and adds it to the request.
        body: t.Any = request.scope.get("form")

        if not body:
            try:
                body = await request.json()
            except SerializationException:
                body = await request.form()

        username = body.get("username", None)
        password = body.get("password", None)
        return_html = body.get("format") == "html"

        if (not username) or (not password):
            error_message = "Missing username or password"
            if return_html:
                alert(request, error_message, level="error")
                return self._render_template(request)
            else:
                raise HTTPException(status_code=422, detail=error_message)

        # Run pre_login hooks
        if self._hooks and self._hooks.pre_login:
            hooks_response = await self._hooks.run_pre_login(username=username)
            if isinstance(hooks_response, str):
                return self._get_error_response(
                    request=request,
                    error=hooks_response,
                )

        # Attempt login
        user_id = await self._auth_table.login(username=username, password=password)

        if user_id:
            # Run login_success hooks
            if self._hooks and self._hooks.login_success:
                hooks_response = await self._hooks.run_login_success(
                    username=username, user_id=user_id
                )
                if isinstance(hooks_response, str):
                    return self._get_error_response(
                        request=request,
                        error=hooks_response,
                    )
        else:
            # Run login_failure hooks
            if self._hooks and self._hooks.login_failure:
                hooks_response = await self._hooks.run_login_failure(username=username)
                if isinstance(hooks_response, str):
                    return self._get_error_response(
                        request=request,
                        error=hooks_response,
                    )

            if return_html:
                alert(request, "The username or password is incorrect.", level="error")
                return self._render_template(request)
            else:
                raise HTTPException(status_code=401, detail="Login failed")

        now = datetime.now()
        expiry_date = now + self._session_expiry
        max_expiry_date = now + self._max_session_expiry

        session: SessionsBase = await self._session_table.create_session(
            user_id=user_id,
            expiry_date=expiry_date,
            max_expiry_date=max_expiry_date,
        )

        # Basic open redirect checks
        if not next_route.startswith("/"):
            next_route = "/"

        response: Redirect = Redirect(next_route)

        if not self._production:
            message = (
                "If running sessions in production, make sure 'production' "
                "is set to True, and serve under HTTPS."
            )
            warnings.warn(message)

        if await has_password_been_pwned(password):
            alert(
                request,
                "Your password appears in breach databases, consider changing it.",
                level="error",
            )

        cookie_value = t.cast(str, session.token)

        response.set_cookie(
            key=self._cookie_name,
            value=cookie_value,
            httponly=True,
            secure=self._production,
            max_age=int(self._max_session_expiry.total_seconds()),
            samesite="lax",
        )
        return response

from litestar import Response, MediaType
from litestar.exceptions import NotFoundException
from litestar.response import Redirect, Template


class RedirectForAuth(Exception):
    """Mark this authentication failure as a request to receive it"""

    def __init__(self, next_route: str):
        self.next_route = next_route


def redirect_for_auth(_, exc: RedirectForAuth) -> Response[Redirect]:
    """Where auth is required, redirect for it"""
    return Redirect(f"/b/login?next_route={exc.next_route}")

import os
import uuid

import commons
import humanize
import orjson
from dotenv import load_dotenv
from litestar import get, MediaType, route, Request
from litestar.exceptions import NotFoundException
from litestar.response import Template

from home.middleware import EnsureAuth
from home.tables import RequestMade
from home.util import get_csp

load_dotenv()
HIDE_QUERY_PARAMS = os.environ.get("HIDE_QUERY_PARAMS", None) is not None
HIDE_URLS: bool = commons.value_to_bool(os.environ.get("HIDE_URLS"))
IGNORE_FROM_SELF: bool = commons.value_to_bool(os.environ.get("IGNORE_FROM_SELF"))


@get("/b/requests/{request_uuid: str}", middleware=[EnsureAuth])
async def view_authed_request(request_uuid: uuid.UUID) -> Template:
    csp, nonce = get_csp()
    request_made: RequestMade = await RequestMade.objects().get(
        RequestMade.uuid == request_uuid
    )
    if request_made is None:
        raise NotFoundException

    return Template(
        template_name="request.jinja",
        context={
            "title": f"Request {request_made.uuid}",
            "csp_nonce": nonce,
            "request_made": request_made,
            "headers": orjson.loads(request_made.headers),
            "made_at": humanize.naturaldate(request_made.made_at),
            "made_at_time": humanize.naturaltime(request_made.made_at),
        },
        headers={"content-security-policy": csp},
        media_type=MediaType.HTML,
    )


@route(
    ["", "/{full_path:path}"],
    http_method=[
        "GET",
        "POST",
        "HEAD",
        "DELETE",
        "OPTIONS",
        "TRACE",
        "PUT",
        "PATCH",
    ],
)
async def catch_all(request: Request, full_path: str = "/") -> Template:
    request.scope["user"] = await EnsureAuth.get_user_from_connection(
        request, fail_on_not_set=False
    )
    csp, nonce = get_csp()
    if not (IGNORE_FROM_SELF and request.user is not None):
        request_made: RequestMade = RequestMade(
            headers=orjson.dumps(dict(request.headers)).decode("utf-8"),
            body=(await request.body()).decode("utf-8"),
            url=full_path,
            query_params=request.url.query,
            type=request.method,
            domain=request.headers["host"],
        )
        await request_made.save()

    request_query = RequestMade.objects().order_by(RequestMade.id, ascending=False)
    if commons.value_to_bool(os.environ.get("ONLY_SHOW_CURRENT_DOMAIN", False)) is True:
        request_query = request_query.where(
            RequestMade.domain == request.headers["host"]
        )

    requests = await request_query.limit(25)

    return Template(
        template_name="home.jinja",
        context={
            "title": "Incoming requests",
            "csp_nonce": nonce,
            "requests": requests,
            "show_query_params": not HIDE_QUERY_PARAMS,
            "hide_urls": HIDE_URLS,
        },
        headers={"content-security-policy": csp},
        media_type=MediaType.HTML,
    )

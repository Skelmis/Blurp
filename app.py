import os
import secrets
import uuid
from copy import deepcopy
from typing import Annotated

import commons
import humanize
import jinja2
import orjson
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from piccolo_admin.endpoints import create_admin, TableConfig, OrderBy
from piccolo.engine import engine_finder
from starlette import status
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response, RedirectResponse
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

from home.tables import RequestMade

load_dotenv()

hide_query_params = os.environ.get("HIDE_QUERY_PARAMS", None) is not None
headers = {
    "x-frame-options": "SAMEORIGIN",
    "x-content-type-options": "nosniff",
    "referrer-policy": "strict-origin",
    "permissions-policy": "microphone=(); geolocation=(); fullscreen=();",
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'; object-src 'none';"
    " base-uri 'none'; script-src 'nonce-{}' 'strict-dynamic'; style-src 'nonce-{}' "
    "'strict-dynamic'; require-trusted-types-for 'script'; img-src 'nonce-{}'",
}


def get_sec_headers() -> tuple[dict, str]:
    nonce = secrets.token_urlsafe(16)
    local_headers = deepcopy(headers)
    local_headers["content-security-policy"] = local_headers[
        "content-security-policy"
    ].format(nonce, nonce, nonce, nonce)
    return local_headers, nonce


requests_tc = TableConfig(
    RequestMade,
    menu_group="Main",
    order_by=[OrderBy(RequestMade.id, ascending=False)],
)

app = FastAPI(
    routes=[
        Mount(
            "/admin/",
            create_admin(
                tables=[requests_tc],
                allowed_hosts=os.environ.get("SERVING_DOMAIN", "").split(","),
                production=True,
                sidebar_links={"Site root": "/"},
                site_name="Blurp Admin",
                auto_include_related=True,
            ),
        ),
        Mount("/static/", StaticFiles(directory="static")),
    ],
)


ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(
        searchpath=os.path.join(os.path.dirname(__file__), "home", "templates")
    ),
    autoescape=True,
)
security = HTTPBasic()

HIDE_URLS = os.environ.get("HIDE_URLS")
USERNAME = os.environ.get("REQUEST_USERNAME")
PASSWORD = os.environ.get("REQUEST_PASSWORD")
REQUIRES_AUTH = USERNAME is not None and PASSWORD is not None


def get_current_username(
    credentials: Annotated[HTTPBasicCredentials, Depends(security)]
):
    if not REQUIRES_AUTH:
        return "Not required"

    current_username_bytes = credentials.username.encode("utf8")
    correct_username_bytes = USERNAME.encode("utf8")
    is_correct_username = secrets.compare_digest(
        current_username_bytes, correct_username_bytes
    )
    current_password_bytes = credentials.password.encode("utf8")
    correct_password_bytes = PASSWORD.encode("utf8")
    is_correct_password = secrets.compare_digest(
        current_password_bytes, correct_password_bytes
    )
    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials.username


@app.get("/requests/authed/{request_uuid}")
async def view_authed_request(
    request_uuid: uuid.UUID,
    _: Annotated[str, Depends(get_current_username)],
):
    return await view_request(request_uuid)


@app.get("/requests/{request_uuid}")
async def view_no_auth_request(request_uuid: uuid.UUID):
    if not REQUIRES_AUTH:
        return await view_request(request_uuid)

    return RedirectResponse(f"/requests/authed/{request_uuid}")


async def view_request(request_uuid: uuid.UUID):
    request_made: RequestMade = await RequestMade.objects().get(
        RequestMade.uuid == request_uuid
    )
    template = ENVIRONMENT.get_template("request.html.jinja")

    sec_headers, nonce = get_sec_headers()
    content = template.render(
        title=f"Request {request_made.uuid}",
        request=request_made,
        csp_nonce=nonce,
        headers=orjson.loads(request_made.headers),
        made_at=humanize.naturaldate(request_made.made_at),
        made_at_time=humanize.naturaltime(request_made.made_at),
    )
    return HTMLResponse(content, headers=sec_headers)


@app.api_route(
    "/{full_path:path}",
    methods=[
        "GET",
        "POST",
        "HEAD",
        "DELETE",
        "OPTIONS",
        "TRACE",
        "PUT",
        "PATCH",
        "PROPFIND",
    ],
)
async def catch_all(request: Request, full_path: str, response: Response):
    template = ENVIRONMENT.get_template("home.html.jinja")
    request_made: RequestMade = RequestMade(
        headers=orjson.dumps(dict(request.headers)).decode("utf-8"),
        body=(await request.body()).decode("utf-8"),
        url=f"/{full_path}",
        query_params=str(request.query_params),
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

    sec_headers, nonce = get_sec_headers()
    content = template.render(
        title="Incoming requests",
        requests=requests,
        csp_nonce=nonce,
        show_query_params=not hide_query_params,
        authed=REQUIRES_AUTH,
        hide_urls=HIDE_URLS,
    )
    return HTMLResponse(
        content,
        headers=sec_headers,
    )


@app.on_event("startup")
async def open_database_connection_pool():
    try:
        engine = engine_finder()
        await engine.start_connection_pool()
    except Exception:
        print("Unable to connect to the database")


@app.on_event("shutdown")
async def close_database_connection_pool():
    try:
        engine = engine_finder()
        await engine.close_connection_pool()
    except Exception:
        print("Unable to connect to the database")

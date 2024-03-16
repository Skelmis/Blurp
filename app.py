import os
import secrets
import uuid
from typing import Annotated

import humanize
import jinja2
import orjson
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from piccolo_admin.endpoints import create_admin
from piccolo.engine import engine_finder
from starlette import status
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

from home.piccolo_app import APP_CONFIG
from home.tables import RequestMade

load_dotenv()

hide_query_params = os.environ.get("HIDE_QUERY_PARAMS", None) is not None
headers = {
    "x-frame-options": "SAMEORIGIN",
    "x-xss-protection": "1; mode=block",
    "x-content-type-options": "nosniff",
    "referrer-policy": "strict-origin",
    "permissions-policy": "microphone=(); geolocation=(); fullscreen=();",
    # "content-security-policy": "default-src 'none'; script-src 'none'",
}

app = FastAPI(
    routes=[
        Mount(
            "/admin/",
            create_admin(
                tables=APP_CONFIG.table_classes,
                # Required when running under HTTPS:
                # allowed_hosts=['my_site.com']
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


@app.get("/requests/{request_uuid}")
async def view_request(
    request_uuid: uuid.UUID,
    _: Annotated[str, Depends(get_current_username)],
):
    request_made: RequestMade = await RequestMade.objects().get(
        RequestMade.uuid == request_uuid
    )
    template = ENVIRONMENT.get_template("request.html.jinja")

    content = template.render(
        title=f"Request {request_made.uuid}",
        request=request_made,
        headers=orjson.loads(request_made.headers),
        made_at=humanize.naturaldate(request_made.made_at),
        made_at_time=humanize.naturaltime(request_made.made_at),
    )
    return HTMLResponse(content)


@app.api_route(
    "/{full_path:path}",
    methods=["GET", "POST", "HEAD", "DELETE", "OPTIONS", "TRACE", "PUT", "PATCH"],
)
async def catch_all(request: Request, full_path: str, response: Response):
    template = ENVIRONMENT.get_template("home.html.jinja")
    request_made: RequestMade = RequestMade(
        headers=orjson.dumps(dict(request.headers)).decode("utf-8"),
        body=(await request.body()).decode("utf-8"),
        url=f"/{full_path}",
        query_params=str(request.query_params),
        type=request.method,
    )
    await request_made.save()

    requests = (
        await RequestMade.objects().order_by(RequestMade.id, ascending=False).limit(25)
    )

    content = template.render(
        title="Incoming requests",
        requests=requests,
        show_query_params=not hide_query_params,
    )
    return HTMLResponse(
        content,
        headers=headers,
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

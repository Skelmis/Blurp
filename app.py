import os
import secrets

import jinja2
from commons import value_to_bool
from dotenv import load_dotenv
from litestar import Litestar, asgi
from litestar.config.cors import CORSConfig
from litestar.config.csrf import CSRFConfig
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.datastructures import ResponseHeader
from litestar.middleware.rate_limit import RateLimitConfig
from litestar.middleware.session.client_side import CookieBackendConfig
from litestar.openapi import OpenAPIConfig
from litestar.openapi.plugins import SwaggerRenderPlugin
from litestar.plugins.flash import FlashPlugin, FlashConfig
from litestar.static_files import StaticFilesConfig
from litestar.template import TemplateConfig
from litestar.types import Receive, Scope, Send
from piccolo.apps.user.tables import BaseUser
from piccolo.engine import engine_finder
from piccolo_admin.endpoints import create_admin, TableConfig, OrderBy

from home import endpoints, controllers
from home.exception_handlers import RedirectForAuth, redirect_for_auth
from home.tables import RequestMade

load_dotenv()
IS_PRODUCTION = not value_to_bool(os.environ.get("DEBUG"))


# mounting Piccolo Admin
@asgi("/b/admin/", is_mount=True)
async def admin(scope: "Scope", receive: "Receive", send: "Send") -> None:
    user_tc = TableConfig(BaseUser, menu_group="User Management")
    requests_tc = TableConfig(
        RequestMade,
        menu_group="Main",
        order_by=[OrderBy(RequestMade.id, ascending=False)],
        visible_columns=[
            RequestMade.id,
            RequestMade.type,
            RequestMade.domain,
            RequestMade.url,
            RequestMade.query_params,
            RequestMade.made_at,
        ],
    )

    await create_admin(
        tables=[user_tc, requests_tc],
        allowed_hosts=os.environ.get("SERVING_DOMAIN", "").split(","),
        production=IS_PRODUCTION,
        sidebar_links={"Site root": "/"},
        site_name="Blurp Admin",
        auto_include_related=True,
    )(scope, receive, send)


async def open_database_connection_pool():
    try:
        engine = engine_finder()
        await engine.start_connection_pool()
    except Exception:
        print("Unable to connect to the database")


async def close_database_connection_pool():
    try:
        engine = engine_finder()
        await engine.close_connection_pool()
    except Exception:
        print("Unable to connect to the database")


cors_config = CORSConfig(
    allow_origins=[],
    allow_headers=[],
    allow_methods=[],
    allow_credentials=False,
)
CSRF_TOKEN = os.environ.get("CSRF_TOKEN", secrets.token_hex(32))
csrf_config = CSRFConfig(
    secret=CSRF_TOKEN,
    # Aptly named so it doesnt clash
    # with piccolo 'csrftoken' cookies
    cookie_name="csrf_token",
    cookie_secure=True,
    cookie_httponly=True,
    # Exclude routes Piccolo handles itself
    # and our api routes
    exclude=[
        "/b/admin",
        "/b/login",
        "/b/logout",
    ],
)
rate_limit_config = RateLimitConfig(
    rate_limit=("second", 5), exclude=["/b/admin", "/b/docs"]
)
ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(
        searchpath=os.path.join(os.path.dirname(__file__), "home", "templates")
    ),
    autoescape=True,
)
template_config = TemplateConfig(
    directory="home/templates", engine=JinjaTemplateEngine.from_environment(ENVIRONMENT)
)
flash_plugin = FlashPlugin(config=FlashConfig(template_config=template_config))
session_config = CookieBackendConfig(secret=secrets.token_bytes(16))
app = Litestar(
    route_handlers=[
        admin,
        endpoints.view_authed_request,
        endpoints.catch_all,
        controllers.LogoutController,
        controllers.LoginController,
        controllers.PasswordController,
    ],
    template_config=template_config,
    static_files_config=[
        StaticFilesConfig(directories=["static"], path="/static/"),
    ],
    on_startup=[open_database_connection_pool],
    on_shutdown=[close_database_connection_pool],
    debug=not IS_PRODUCTION,
    openapi_config=OpenAPIConfig(
        title="Blurp API",
        version="0.0.0",
        render_plugins=[SwaggerRenderPlugin()],
        path="/b/docs",
    ),
    cors_config=cors_config,
    csrf_config=csrf_config,
    middleware=[rate_limit_config.middleware, session_config.middleware],
    plugins=[flash_plugin],
    response_headers=[
        ResponseHeader(
            name="x-frame-options",
            value="SAMEORIGIN",
            description="Security header",
        ),
        ResponseHeader(
            name="x-content-type-options",
            value="nosniff",
            description="Security header",
        ),
        ResponseHeader(
            name="referrer-policy",
            value="strict-origin",
            description="Security header",
        ),
        ResponseHeader(
            name="x-xss-protection",
            value="1; mode=block",
            description="Security header",
        ),
        ResponseHeader(
            name="permissions-policy",
            value="microphone=(); geolocation=(); fullscreen=();",
            description="Security header",
        ),
        ResponseHeader(
            name="content-security-policy",
            value="default-src 'none'; frame-ancestors 'none'; object-src 'none';"
            " base-uri 'none'; script-src 'nonce-{}' 'strict-dynamic'; style-src "
            "'nonce-{}' 'strict-dynamic'; require-trusted-types-for 'script'",
            description="Security header",
            documentation_only=True,
        ),
    ],
    exception_handlers={
        RedirectForAuth: redirect_for_auth,
    },
)

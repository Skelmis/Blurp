import os

from dotenv import load_dotenv
from piccolo.engine.postgres import PostgresEngine
from piccolo.engine.sqlite import SQLiteEngine

from piccolo.conf.apps import AppRegistry

load_dotenv()

if os.environ.get("PROD", None) is not None:
    DB = PostgresEngine(
        config={
            "database": os.environ["POSTGRES_DB"],
            "user": os.environ["POSTGRES_USER"],
            "password": os.environ["POSTGRES_PASSWORD"],
            "host": os.environ["POSTGRES_HOST"],
            "port": int(os.environ["POSTGRES_PORT"]),
        },
        extensions=tuple(),
    )
else:
    DB = SQLiteEngine()

APP_REGISTRY = AppRegistry(apps=["home.piccolo_app", "piccolo_admin.piccolo_app"])

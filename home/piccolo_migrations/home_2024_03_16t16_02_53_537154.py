from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from piccolo.columns.column_types import Text
from piccolo.columns.indexes import IndexMethod


ID = "2024-03-16T16:02:53:537154"
VERSION = "1.4.2"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="home", description=DESCRIPTION
    )

    manager.drop_column(
        table_class_name="RequestMade",
        tablename="request_made",
        column_name="host",
        db_column_name="host",
        schema=None,
    )

    manager.add_column(
        table_class_name="RequestMade",
        tablename="request_made",
        column_name="query_params",
        db_column_name="query_params",
        column_class_name="Text",
        column_class=Text,
        params={
            "default": "",
            "null": False,
            "primary_key": False,
            "unique": False,
            "index": False,
            "index_method": IndexMethod.btree,
            "choices": None,
            "db_column_name": None,
            "secret": False,
        },
        schema=None,
    )

    return manager

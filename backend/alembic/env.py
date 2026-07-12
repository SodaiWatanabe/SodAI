import asyncio
from logging.config import fileConfig

from sqlalchemy import inspect, pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app import models as _models  # noqa: F401
from app.core.config import get_settings
from app.db.base import APPLICATION_SCHEMA, Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ConfigParser treats percent-encoded password characters as interpolation.
config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))
target_metadata = Base.metadata


def include_name(name: str | None, type_: str, parent_names: dict[str, str | None]) -> bool:
    if type_ == "schema":
        return name in {None, APPLICATION_SCHEMA}
    if type_ == "table":
        return parent_names["schema_qualified_table_name"] in target_metadata.tables
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_name=include_name,
        version_table_schema=APPLICATION_SCHEMA,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    if not inspect(connection).has_schema(APPLICATION_SCHEMA):
        raise RuntimeError(
            "PostgreSQL schema 'app' is missing. Initialize the self-hosted "
            "infrastructure before running application migrations."
        )
    connection.execute(text("SET LOCAL search_path TO public"))
    connection.dialect.default_schema_name = "public"
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        include_name=include_name,
        version_table_schema=APPLICATION_SCHEMA,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    # Schema existence inspection starts SQLAlchemy's implicit transaction.
    # Own that transaction here so both the inspection and Alembic DDL commit
    # together instead of being rolled back when the connection closes.
    async with connectable.begin() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

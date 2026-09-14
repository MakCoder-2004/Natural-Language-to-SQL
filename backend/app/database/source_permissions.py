"""Read-only source-role verification using PostgreSQL privilege metadata."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database.errors import (
    DatabasePermissionError,
    DatabaseServiceError,
    SourceIntrospectionError,
)
from app.database.models import DatabaseIdentity, SourceSchemaSnapshot
from app.database.source_connection import SourceDatabase

_ROLE_ACCESS_SQL = text(
    """
    WITH RECURSIVE role_tree(role_oid) AS (
        SELECT oid
        FROM pg_catalog.pg_roles
        WHERE rolname = current_user
        UNION
        SELECT membership.roleid
        FROM pg_catalog.pg_auth_members AS membership
        JOIN role_tree ON role_tree.role_oid = membership.member
    )
    SELECT
        current_database() AS database_name,
        current_user AS user_name,
        current_setting('server_version') AS server_version,
        current_setting('transaction_read_only') = 'on' AS transaction_read_only,
        has_database_privilege(current_user, current_database(), 'CREATE') AS can_create_database,
        COALESCE(bool_or(role_data.rolsuper), false) AS has_superuser_role,
        COALESCE(bool_or(role_data.rolcreaterole), false) AS has_create_role,
        COALESCE(bool_or(role_data.rolcreatedb), false) AS has_create_database_role,
        COALESCE(bool_or(role_data.rolreplication), false) AS has_replication_role,
        COALESCE(bool_or(role_data.rolbypassrls), false) AS has_bypass_rls_role
    FROM role_tree
    JOIN pg_catalog.pg_roles AS role_data ON role_data.oid = role_tree.role_oid
    """
)

_SCHEMA_ACCESS_SQL = text(
    """
    SELECT
        has_schema_privilege(current_user, :schema_name, 'USAGE') AS can_use,
        has_schema_privilege(current_user, :schema_name, 'CREATE') AS can_create
    """
)

_RELATION_ACCESS_SQL = text(
    """
    SELECT
        has_table_privilege(
            current_user,
            format('%I.%I', :schema_name, :relation_name),
            'SELECT'
        ) AS can_select,
        has_table_privilege(
            current_user,
            format('%I.%I', :schema_name, :relation_name),
            'INSERT'
        ) AS can_insert,
        has_table_privilege(
            current_user,
            format('%I.%I', :schema_name, :relation_name),
            'UPDATE'
        ) AS can_update,
        has_table_privilege(
            current_user,
            format('%I.%I', :schema_name, :relation_name),
            'DELETE'
        ) AS can_delete,
        has_table_privilege(
            current_user,
            format('%I.%I', :schema_name, :relation_name),
            'TRUNCATE'
        ) AS can_truncate,
        has_table_privilege(
            current_user,
            format('%I.%I', :schema_name, :relation_name),
            'REFERENCES'
        ) AS can_references,
        has_table_privilege(
            current_user,
            format('%I.%I', :schema_name, :relation_name),
            'TRIGGER'
        ) AS can_trigger,
        pg_has_role(current_user, relation_data.relowner, 'member') AS owns_relation
    FROM pg_catalog.pg_class AS relation_data
    JOIN pg_catalog.pg_namespace AS namespace_data
        ON namespace_data.oid = relation_data.relnamespace
    WHERE namespace_data.nspname = :schema_name
      AND relation_data.relname = :relation_name
      AND relation_data.relkind IN ('r', 'p', 'v', 'm', 'f')
    """
)


@dataclass(frozen=True, slots=True)
class ReadOnlyAccessReport:
    """Safe result of source-role verification."""

    identity: DatabaseIdentity
    transaction_read_only: bool
    checked_schema_count: int
    checked_relation_count: int


def verify_source_read_only_access(
    database: SourceDatabase, snapshot: SourceSchemaSnapshot | None = None
) -> ReadOnlyAccessReport:
    """Verify configured source access without issuing writes or DDL."""

    try:
        with database.connect() as connection:
            role_row = connection.execute(_ROLE_ACCESS_SQL).mappings().one()
            identity = DatabaseIdentity(
                database_name=str(role_row["database_name"]),
                user_name=str(role_row["user_name"]),
                server_version=str(role_row["server_version"]),
            )
            if any(
                bool(role_row[field])
                for field in (
                    "can_create_database",
                    "has_superuser_role",
                    "has_create_role",
                    "has_create_database_role",
                    "has_replication_role",
                    "has_bypass_rls_role",
                )
            ):
                raise DatabasePermissionError(
                    "The source database role has permissions beyond read-only access."
                )

            relation_count = 0
            for schema_name in database.schema_scope:
                schema_row = (
                    connection.execute(_SCHEMA_ACCESS_SQL, {"schema_name": schema_name})
                    .mappings()
                    .one()
                )
                if not bool(schema_row["can_use"]) or bool(schema_row["can_create"]):
                    raise DatabasePermissionError(
                        "The source database role has invalid schema permissions."
                    )

            if snapshot is not None:
                for schema in snapshot.schemas:
                    for relation in schema.relations:
                        relation_row = (
                            connection.execute(
                                _RELATION_ACCESS_SQL,
                                {
                                    "schema_name": relation.schema_name,
                                    "relation_name": relation.name,
                                },
                            )
                            .mappings()
                            .one_or_none()
                        )
                        if relation_row is None or not bool(relation_row["can_select"]):
                            raise DatabasePermissionError(
                                "The source database role cannot read an approved relation."
                            )
                        if any(
                            bool(relation_row[field])
                            for field in (
                                "can_insert",
                                "can_update",
                                "can_delete",
                                "can_truncate",
                                "can_references",
                                "can_trigger",
                                "owns_relation",
                            )
                        ):
                            raise DatabasePermissionError(
                                "The source database role has mutation permissions."
                            )
                        relation_count += 1
    except DatabaseServiceError:
        raise
    except SQLAlchemyError as exc:
        raise SourceIntrospectionError("Source read-only access could not be verified.") from exc

    return ReadOnlyAccessReport(
        identity=identity,
        transaction_read_only=bool(role_row["transaction_read_only"]),
        checked_schema_count=len(database.schema_scope),
        checked_relation_count=relation_count,
    )

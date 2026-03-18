"""Store and retrieve uploaded document texts.

Books are 200-500K characters. Stored as TEXT columns in the database.
Each document has a unique doc_id for referencing from execution plans.
"""

import hashlib
import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from src.executor.db import _is_postgres, execute, get_connection, init_db

logger = logging.getLogger(__name__)

VALID_BINDING_ROLES = {"target", "prior_work", "context", "chapter"}


def compute_content_hash(text: str) -> str:
    """Compute the canonical Stage 6 document hash."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _adapt_sql(sql: str) -> str:
    return sql if _is_postgres() else sql.replace("%s", "?")


def _row_to_dict(cursor, row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    if _is_postgres():
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))
    return dict(row)


def _store_document_with_cursor(
    cursor,
    *,
    title: str,
    text: str,
    author: Optional[str],
    role: str,
    doc_id: Optional[str] = None,
) -> str:
    if doc_id is None:
        doc_id = f"doc-{uuid.uuid4().hex[:12]}"

    now = datetime.utcnow().isoformat()
    char_count = len(text)
    content_hash = compute_content_hash(text)
    cursor.execute(
        _adapt_sql(
            """INSERT INTO executor_documents
               (doc_id, title, author, role, text, char_count, content_hash, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
        ),
        (doc_id, title, author, role, text, char_count, content_hash, now),
    )
    return doc_id


def store_document(
    title: str,
    text: str,
    *,
    author: Optional[str] = None,
    role: str = "target",
    doc_id: Optional[str] = None,
) -> str:
    """Store a document text. Returns the doc_id."""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        doc_id = _store_document_with_cursor(
            cursor,
            title=title,
            text=text,
            author=author,
            role=role,
            doc_id=doc_id,
        )
        conn.commit()

    logger.info(
        f"Stored document {doc_id}: '{title}' by {author or 'unknown'}, "
        f"{len(text):,} chars, role={role}"
    )
    return doc_id


def get_document(doc_id: str) -> Optional[dict]:
    """Retrieve a document by ID. Returns dict with all fields including text."""
    return execute(
        "SELECT * FROM executor_documents WHERE doc_id = %s",
        (doc_id,),
        fetch="one",
    )


def get_document_text(doc_id: str) -> Optional[str]:
    """Retrieve just the text of a document."""
    row = execute(
        "SELECT text FROM executor_documents WHERE doc_id = %s",
        (doc_id,),
        fetch="one",
    )
    return row["text"] if row else None


def list_documents(role: Optional[str] = None) -> list[dict]:
    """List documents (without full text for performance)."""
    if role:
        rows = execute(
            """SELECT doc_id, title, author, role, char_count, content_hash, created_at
               FROM executor_documents WHERE role = %s
               ORDER BY created_at DESC""",
            (role,),
            fetch="all",
        )
    else:
        rows = execute(
            """SELECT doc_id, title, author, role, char_count, content_hash, created_at
               FROM executor_documents
               ORDER BY created_at DESC""",
            fetch="all",
        )
    return rows


def delete_document(doc_id: str) -> bool:
    """Delete a document. Returns True if it existed."""
    row = execute(
        "SELECT doc_id FROM executor_documents WHERE doc_id = %s",
        (doc_id,),
        fetch="one",
    )
    if row is None:
        return False
    execute("DELETE FROM executor_documents WHERE doc_id = %s", (doc_id,))
    logger.info(f"Deleted document {doc_id}")
    return True


def _load_existing_bindings(cursor, consumer_key: str, external_project_id: str, external_doc_keys: list[str]) -> dict[str, dict[str, Any]]:
    if not external_doc_keys:
        return {}
    placeholders = ", ".join(["%s"] * len(external_doc_keys))
    cursor.execute(
        _adapt_sql(
            f"""SELECT *
                FROM external_document_bindings
                WHERE consumer_key = %s
                  AND external_project_id = %s
                  AND external_doc_key IN ({placeholders})"""
        ),
        (consumer_key, external_project_id, *external_doc_keys),
    )
    rows = cursor.fetchall()
    return {
        row_dict["external_doc_key"]: row_dict
        for row_dict in (_row_to_dict(cursor, row) for row in rows)
    }


def sync_external_documents(
    *,
    consumer_key: str,
    external_project_id: str,
    documents: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Atomically sync a consumer-owned document inventory into analyzer-v2."""
    init_db()
    if not consumer_key:
        raise ValueError("consumer_key is required")
    if not external_project_id:
        raise ValueError("external_project_id is required")
    if not documents:
        raise ValueError("documents must not be empty")

    external_doc_keys = [str(doc.get("external_doc_key") or "") for doc in documents]
    if any(not key for key in external_doc_keys):
        raise ValueError("Each synced document requires external_doc_key")
    if len(set(external_doc_keys)) != len(external_doc_keys):
        raise ValueError("external_doc_key values must be unique within a sync batch")

    batch_roles: dict[str, str] = {}
    for doc in documents:
        role = doc.get("binding_role")
        if role not in VALID_BINDING_ROLES:
            raise ValueError(f"Unsupported binding_role: {role}")
        supplied_hash = doc.get("content_hash") or ""
        computed_hash = compute_content_hash(doc.get("text") or "")
        if supplied_hash != computed_hash:
            raise ValueError(
                f"content_hash mismatch for external_doc_key='{doc['external_doc_key']}'"
            )
        if role == "chapter":
            if not doc.get("parent_external_doc_key"):
                raise ValueError(
                    f"Chapter '{doc['external_doc_key']}' requires parent_external_doc_key"
                )
        elif doc.get("parent_external_doc_key"):
            raise ValueError(
                f"Non-chapter '{doc['external_doc_key']}' cannot set parent_external_doc_key"
            )
        batch_roles[doc["external_doc_key"]] = role

    with get_connection() as conn:
        cursor = conn.cursor()
        existing_by_key = _load_existing_bindings(cursor, consumer_key, external_project_id, external_doc_keys)
        available_parents = set(existing_by_key) | set(batch_roles)
        for doc in documents:
            if doc["binding_role"] != "chapter":
                continue
            parent_key = doc.get("parent_external_doc_key")
            if parent_key not in available_parents:
                raise ValueError(
                    f"Missing parent_external_doc_key '{parent_key}' for chapter '{doc['external_doc_key']}'"
                )
            parent_role = batch_roles.get(parent_key) or existing_by_key.get(parent_key, {}).get("binding_role")
            if parent_role == "chapter":
                raise ValueError(
                    f"Chapter '{doc['external_doc_key']}' cannot use chapter '{parent_key}' as parent"
                )

        now = datetime.utcnow().isoformat()
        results: list[dict[str, str]] = []
        for doc in documents:
            existing = existing_by_key.get(doc["external_doc_key"])
            computed_hash = doc["content_hash"]
            if existing and existing.get("content_hash") == computed_hash and existing.get("doc_id"):
                doc_id = existing["doc_id"]
                sync_status = "unchanged"
            else:
                doc_id = _store_document_with_cursor(
                    cursor,
                    title=doc["title"],
                    text=doc["text"],
                    author=doc.get("author"),
                    role=doc["binding_role"],
                )
                sync_status = "updated" if existing else "created"

            if existing:
                cursor.execute(
                    _adapt_sql(
                        """UPDATE external_document_bindings
                           SET parent_external_doc_key = %s,
                               doc_id = %s,
                               binding_role = %s,
                               title = %s,
                               author = %s,
                               source_thinker_id = %s,
                               source_thinker_name = %s,
                               source_document_id = %s,
                               content_hash = %s,
                               updated_at = %s
                           WHERE consumer_key = %s
                             AND external_project_id = %s
                             AND external_doc_key = %s"""
                    ),
                    (
                        doc.get("parent_external_doc_key"),
                        doc_id,
                        doc["binding_role"],
                        doc["title"],
                        doc.get("author"),
                        doc.get("source_thinker_id"),
                        doc.get("source_thinker_name"),
                        doc.get("source_document_id"),
                        computed_hash,
                        now,
                        consumer_key,
                        external_project_id,
                        doc["external_doc_key"],
                    ),
                )
            else:
                cursor.execute(
                    _adapt_sql(
                        """INSERT INTO external_document_bindings
                           (consumer_key, external_project_id, external_doc_key,
                            parent_external_doc_key, doc_id, binding_role, title, author,
                            source_thinker_id, source_thinker_name, source_document_id,
                            content_hash, created_at, updated_at)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                    ),
                    (
                        consumer_key,
                        external_project_id,
                        doc["external_doc_key"],
                        doc.get("parent_external_doc_key"),
                        doc_id,
                        doc["binding_role"],
                        doc["title"],
                        doc.get("author"),
                        doc.get("source_thinker_id"),
                        doc.get("source_thinker_name"),
                        doc.get("source_document_id"),
                        computed_hash,
                        now,
                        now,
                    ),
                )

            results.append(
                {
                    "external_doc_key": doc["external_doc_key"],
                    "doc_id": doc_id,
                    "content_hash": computed_hash,
                    "sync_status": sync_status,
                }
            )

        conn.commit()

    logger.info(
        "Synced %s external documents for consumer=%s project=%s",
        len(results),
        consumer_key,
        external_project_id,
    )
    return results


def load_registered_documents(
    *,
    consumer_key: str,
    external_project_id: str,
    external_doc_keys: list[str],
) -> dict[str, dict[str, Any]]:
    """Resolve a batch of external document keys to current bound texts."""
    init_db()
    if not external_doc_keys:
        return {}
    placeholders = ", ".join(["%s"] * len(external_doc_keys))
    rows = execute(
        f"""SELECT b.consumer_key,
                   b.external_project_id,
                   b.external_doc_key,
                   b.parent_external_doc_key,
                   b.doc_id,
                   b.binding_role,
                   b.title,
                   b.author,
                   b.source_thinker_id,
                   b.source_thinker_name,
                   b.source_document_id,
                   b.content_hash,
                   b.created_at,
                   b.updated_at,
                   d.text,
                   d.char_count
            FROM external_document_bindings b
            JOIN executor_documents d ON d.doc_id = b.doc_id
            WHERE b.consumer_key = %s
              AND b.external_project_id = %s
              AND b.external_doc_key IN ({placeholders})""",
        (consumer_key, external_project_id, *external_doc_keys),
        fetch="all",
    )
    return {row["external_doc_key"]: row for row in rows}

"""Store and retrieve uploaded document texts.

Books are 200-500K characters. Stored as TEXT columns in the database.
Each document has a unique doc_id for referencing from execution plans.
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

from src.executor.db import execute

logger = logging.getLogger(__name__)


def store_document(
    title: str,
    text: str,
    *,
    author: Optional[str] = None,
    role: str = "target",
    doc_id: Optional[str] = None,
) -> str:
    """Store a document text. Returns the doc_id."""
    if doc_id is None:
        doc_id = f"doc-{uuid.uuid4().hex[:12]}"

    now = datetime.utcnow().isoformat()
    char_count = len(text)

    execute(
        """INSERT INTO executor_documents
           (doc_id, title, author, role, text, char_count, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (doc_id, title, author, role, text, char_count, now),
    )

    logger.info(
        f"Stored document {doc_id}: '{title}' by {author or 'unknown'}, "
        f"{char_count:,} chars, role={role}"
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
            """SELECT doc_id, title, author, role, char_count, created_at
               FROM executor_documents WHERE role = %s
               ORDER BY created_at DESC""",
            (role,),
            fetch="all",
        )
    else:
        rows = execute(
            """SELECT doc_id, title, author, role, char_count, created_at
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

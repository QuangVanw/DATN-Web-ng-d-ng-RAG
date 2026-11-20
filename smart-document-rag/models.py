import pymysql
from flask import current_app, g


def connection():
    if "mysql" not in g:
        config = current_app.config
        g.mysql = pymysql.connect(
            host=config["MYSQL_HOST"],
            port=config["MYSQL_PORT"],
            user=config["MYSQL_USER"],
            password=config["MYSQL_PASSWORD"],
            database=config["MYSQL_DATABASE"],
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
        )
    return g.mysql


def close_connection(_error=None):
    db = g.pop("mysql", None)
    if db is not None:
        db.close()


def find_admin(username):
    with connection().cursor() as cursor:
        cursor.execute("SELECT id, password_hash FROM admins WHERE username = %s", (username,))
        return cursor.fetchone()


def create_admin(username, password_hash):
    if accounts_ready():
        with connection().cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (fullname, username, password_hash, role) VALUES (%s, %s, %s, 'admin')",
                (username, username, password_hash),
            )
        return
    with connection().cursor() as cursor:
        cursor.execute(
            "INSERT INTO admins (username, password_hash) VALUES (%s, %s)",
            (username, password_hash),
        )


def list_documents(account, *, own=False, limit=None):
    scope, params = _document_scope(account, own=own)
    limit_clause = ""
    if limit is not None:
        limit_clause = " LIMIT %s"
        params = (*params, limit)
    with connection().cursor() as cursor:
        cursor.execute(
            f"""SELECT d.id, d.filename, d.file_type, d.size_bytes, d.created_at
                FROM documents AS d WHERE {scope} ORDER BY d.id DESC""" + limit_clause,
            params,
        )
        return cursor.fetchall()


def count_documents(account, *, own=False):
    scope, params = _document_scope(account, own=own)
    with connection().cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) AS total FROM documents AS d WHERE {scope}", params)
        return cursor.fetchone()["total"]



def find_document(document_id, account):
    scope, params = _document_scope(account)
    with connection().cursor() as cursor:
        cursor.execute(f"SELECT d.* FROM documents AS d WHERE d.id = %s AND {scope}", (document_id, *params))
        return cursor.fetchone()


def create_document(filename, file_type, size_bytes, content, account):
    with connection().cursor() as cursor:
        if account.get("legacy"):
            cursor.execute(
                "INSERT INTO documents (filename, file_type, size_bytes, content) VALUES (%s, %s, %s, %s)",
                (filename, file_type, size_bytes, content),
            )
        else:
            cursor.execute(
                "INSERT INTO documents (filename, file_type, size_bytes, content, user_id) "
                "VALUES (%s, %s, %s, %s, %s)",
                (filename, file_type, size_bytes, content, account["id"]),
            )
        return cursor.lastrowid


def delete_document(document_id, account):
    scope, params = _document_scope(account)
    with connection().cursor() as cursor:
        return cursor.execute(
            f"DELETE d FROM documents AS d WHERE d.id = %s AND {scope}",
            (document_id, *params),
        ) == 1



def search_documents(keyword, account):
    scope, params = _document_scope(account)
    with connection().cursor() as cursor:
        cursor.execute(
            f"""
            SELECT id, filename, file_type,
                   SUBSTRING(content, GREATEST(match_position - 100, 1),
                             CHAR_LENGTH(%s) + 200) AS snippet
            FROM (
                SELECT id, filename, file_type, content,
                       LOCATE(%s, content COLLATE utf8mb4_unicode_ci) AS match_position
                FROM documents AS d WHERE {scope}
            ) AS matches
            WHERE match_position > 0
            ORDER BY id DESC
            LIMIT 51
            """,
            (keyword, keyword, *params),
        )
        return cursor.fetchall()


def supports_chunk_pages():
    if "supports_chunk_pages" not in g:
        with connection().cursor() as cursor:
            cursor.execute("SHOW COLUMNS FROM document_chunks LIKE 'page_number'")
            g.supports_chunk_pages = cursor.fetchone() is not None
    return g.supports_chunk_pages


def insert_chunks(document_id, chunks):
    with connection().cursor() as cursor:
        if supports_chunk_pages():
            cursor.executemany(
                "INSERT INTO document_chunks (document_id, chunk_index, content, page_number) "
                "VALUES (%s, %s, %s, %s)",
                [(document_id, c["chunk_index"], c["content"], c["page_number"]) for c in chunks],
            )
        else:
            cursor.executemany(
                "INSERT INTO document_chunks (document_id, chunk_index, content) VALUES (%s, %s, %s)",
                [(document_id, c["chunk_index"], c["content"]) for c in chunks],
            )


def retrieval_rows(account):
    scope, params = _document_scope(account)
    page = "c.page_number" if supports_chunk_pages() else "NULL"
    with connection().cursor() as cursor:
        cursor.execute(
            f"""
            SELECT d.id AS document_id, d.filename, c.chunk_index, {page} AS page_number,
                   CASE WHEN c.chunk_index IS NULL THEN d.content ELSE c.content END AS content
            FROM documents AS d
            LEFT JOIN document_chunks AS c ON c.document_id = d.id
            WHERE {scope}
            ORDER BY c.chunk_index IS NULL, d.id, c.chunk_index
            """,
            params,
        )
        return cursor.fetchall()



def supports_docx():
    with connection().cursor() as cursor:
        cursor.execute("SHOW COLUMNS FROM documents LIKE 'file_type'")
        column = cursor.fetchone()
        return column is not None and "'docx'" in column["Type"]


def list_admins():
    with connection().cursor() as cursor:
        if accounts_ready():
            cursor.execute("SELECT username FROM users WHERE role = 'admin' ORDER BY username")
        else:
            cursor.execute("SELECT username FROM admins ORDER BY username")
        return cursor.fetchall()


ACCOUNT_COLUMNS = "id, username, fullname, role, search_count, chat_count"


def accounts_ready():
    if "accounts_ready" not in g:
        with connection().cursor() as cursor:
            try:
                cursor.execute("SELECT fullname, search_count, chat_count FROM users LIMIT 0")
                cursor.execute("SELECT user_id FROM documents LIMIT 0")
            except pymysql.MySQLError as error:
                if error.args[0] not in (1054, 1146):
                    raise
                g.accounts_ready = False
            else:
                g.accounts_ready = True
    return g.accounts_ready


def load_account(account_id, legacy=False):
    with connection().cursor() as cursor:
        if legacy:
            cursor.execute(
                """SELECT id, username, username AS fullname, 'admin' AS role
                   FROM admins WHERE id = %s""",
                (account_id,),
            )
        else:
            cursor.execute(f"SELECT {ACCOUNT_COLUMNS} FROM users WHERE id = %s", (account_id,))
        return cursor.fetchone()


def find_user(username):
    with connection().cursor() as cursor:
        cursor.execute(
            f"SELECT {ACCOUNT_COLUMNS}, password_hash FROM users WHERE username = %s",
            (username,),
        )
        return cursor.fetchone()


def register_user(fullname, username, email, password_hash):
    with connection().cursor() as cursor:
        cursor.execute(
            "INSERT INTO users (fullname, username, email, password_hash, role) "
            "VALUES (%s, %s, %s, %s, 'user')",
            (fullname, username, email, password_hash),
        )


def record_activity(account, *, chat=False):
    if account.get("legacy"):
        return
    column = "chat_count" if chat else "search_count"
    with connection().cursor() as cursor:
        cursor.execute(f"UPDATE users SET {column} = {column} + 1 WHERE id = %s", (account["id"],))


def _document_scope(account, *, own=False):
    if account["role"] == "admin" and (not own or account.get("legacy")):
        return "1 = 1", ()
    return "d.user_id = %s", (account["id"],)

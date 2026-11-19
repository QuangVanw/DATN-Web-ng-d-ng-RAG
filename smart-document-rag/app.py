import hmac
import re
import secrets
from datetime import datetime
from functools import wraps
from io import BytesIO
from pathlib import Path

import click
from flask import (
    Flask, abort, flash, g, redirect, render_template, request, send_file, session, url_for,
)
from pymysql.err import IntegrityError, MySQLError, ProgrammingError
from werkzeug.security import check_password_hash, generate_password_hash

import models
import rag
from config import Config
from document_files import extract_document


def login_required(view):
    @wraps(view)
    def protected(*args, **kwargs):
        if not g.account:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return protected


def registration_error(fields, password, confirmation):
    if not 1 <= len(fields["fullname"]) <= 120 or not fields["fullname"].isprintable():
        return "Họ tên phải có từ 1 đến 120 ký tự."
    if not re.fullmatch(r"[a-zA-Z0-9_.-]{3,80}", fields["username"]):
        return "Tên đăng nhập cần từ 3 đến 80 ký tự gồm chữ không dấu, số, dấu chấm, gạch dưới hoặc gạch ngang."
    if len(fields["email"]) > 254 or not re.fullmatch(
        r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+",
        fields["email"],
    ):
        return "Hãy nhập địa chỉ email hợp lệ."
    if not 8 <= len(password) <= 128:
        return "Mật khẩu phải có từ 8 đến 128 ký tự."
    if password != confirmation:
        return "Mật khẩu xác nhận không khớp."
    return None



def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    if not app.secret_key:
        raise RuntimeError("Hãy đặt SECRET_KEY trong tệp .env.")

    app.teardown_appcontext(models.close_connection)

    @app.template_filter("document_date")
    def document_date(value, pattern="%d/%m/%Y"):
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                return value
        return value.strftime(pattern) if value else "—"

    @app.cli.command("create-admin")
    @click.argument("username")
    @click.password_option()
    def create_admin(username, password):
        username = username.strip()
        if not username or len(username) > 80:
            raise click.ClickException("Tên đăng nhập phải có từ 1 đến 80 ký tự.")
        if len(password) < 8:
            raise click.ClickException("Mật khẩu phải có ít nhất 8 ký tự.")
        try:
            models.create_admin(username, generate_password_hash(password))
        except IntegrityError as error:
            raise click.ClickException("Tên đăng nhập đã tồn tại.") from error
        click.echo("Đã tạo tài khoản quản trị.")

    @app.context_processor
    def form_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        def asset_url(filename):
            version = Path(app.static_folder, filename).stat().st_mtime_ns
            return url_for("static", filename=filename, v=version)

        return {"csrf_token": session["csrf_token"], "asset_url": asset_url}

    @app.before_request
    def load_current_account():
        g.account = None
        if request.endpoint == "static" or not (session.get("user_id") or session.get("admin_id")):
            return
        migrated = models.accounts_ready()
        account_id = session.get("user_id" if migrated else "admin_id")
        if account_id:
            g.account = models.load_account(account_id, legacy=not migrated)
            if g.account:
                g.account["legacy"] = not migrated
                return
        session.clear()


    @app.before_request
    def verify_form_token():
        if request.endpoint == "upload_document":
            request.max_content_length = (
                app.config["MAX_UPLOAD_BYTES"] * app.config["MAX_UPLOAD_FILES"] + 1024 * 1024
            )
        if request.method == "POST":
            expected = session.get("csrf_token")
            token = request.form.get("csrf_token", "")
            if not expected or not hmac.compare_digest(expected.encode(), token.encode()):
                abort(400, "Biểu mẫu đã hết hạn hoặc không hợp lệ. Hãy tải lại trang.")

    @app.errorhandler(413)
    def upload_too_large(_error):
        if not g.account:
            return redirect(url_for("login"))
        flash("Yêu cầu tải lên vượt quá giới hạn dung lượng.", "error")
        return render_template("documents.html", documents=models.list_documents(g.account)), 413

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if g.account:
            return redirect(url_for("index"))
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            migrated = models.accounts_ready()
            account = None
            if 0 < len(username) <= 80:
                account = models.find_user(username) if migrated else models.find_admin(username)
            if account and check_password_hash(account["password_hash"], password):
                session.clear()
                session["user_id" if migrated else "admin_id"] = account["id"]
                return redirect(url_for("index"))
            flash("Tên đăng nhập hoặc mật khẩu không đúng.", "error")
        return render_template("login.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if g.account:
            return redirect(url_for("index"))
        ready = models.accounts_ready()
        fields = {}
        if request.method == "POST" and ready:
            fields = {
                name: request.form.get(name, "").strip()
                for name in ("fullname", "email", "username")
            }
            fields["email"] = fields["email"].lower()
            password = request.form.get("password", "")
            confirmation = request.form.get("confirm_password", "")
            error = registration_error(fields, password, confirmation)
            if error:
                flash(error, "error")
                return render_template("register.html", ready=ready, fields=fields), 400
            try:
                models.register_user(
                    fields["fullname"], fields["username"], fields["email"],
                    generate_password_hash(password),
                )
            except IntegrityError as exc:
                if exc.args[0] != 1062:
                    raise
                flash("Tên đăng nhập hoặc email đã được sử dụng.", "error")
                return render_template("register.html", ready=ready, fields=fields), 409
            flash("Đăng ký thành công. Bạn có thể đăng nhập ngay.", "success")
            return redirect(url_for("login"), code=303)
        status = 503 if request.method == "POST" else 200
        return render_template("register.html", ready=ready, fields=fields), status


    @app.post("/logout")
    @login_required
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/")
    @login_required
    def index():
        documents = models.list_documents(g.account, own=True)
        return render_template("index.html", document_count=len(documents), recent=documents[:5])

    @app.get("/documents")
    @login_required
    def documents():
        return render_template("documents.html", documents=models.list_documents(g.account))

    @app.get("/search")
    @login_required
    def search():
        keyword = request.args.get("q", "").strip()
        if len(keyword) > 200:
            return render_template(
                "search.html", keyword=keyword, error="Từ khóa tối đa 200 ký tự."
            ), 400
        matches = models.search_documents(keyword, g.account) if keyword else []
        if keyword:
            models.record_activity(g.account)
        return render_template(
            "search.html", keyword=keyword, results=matches[:50], has_more=len(matches) > 50
        )


    @app.route("/chat", methods=["GET", "POST"])
    @login_required
    def chat():
        question = ""
        answer, error, sources = None, None, []
        status = 200
        if request.method == "POST":
            question = request.form.get("question", "").strip()
            if not question or len(question) > rag.QUESTION_LIMIT:
                error = f"Hãy nhập câu hỏi từ 1 đến {rag.QUESTION_LIMIT} ký tự."
                status = 400
            else:
                try:
                    for document_id in models.unindexed_document_ids(g.account):
                        models.index_document(document_id, rag.split_document, g.account)
                    chunks = rag.retrieve(question, models.list_chunks(g.account))
                    if chunks:
                        answer, sources = rag.answer_question(question, chunks, app.config)
                    else:
                        answer = rag.INSUFFICIENT
                    models.record_activity(g.account, chat=True)
                except rag.AnswerError as exc:
                    error = str(exc)
                    status = 503
                except ProgrammingError as exc:
                    if exc.args[0] != 1146:
                        raise
                    error = "Hãy import lại database/schema.sql để tạo bảng đoạn văn."
                    status = 503

        return render_template(
            "chat.html", question=question, question_limit=rag.QUESTION_LIMIT,
            llm_configured=bool(app.config["LLM_API_KEY"] and app.config["LLM_MODEL"]),
            answer=answer, sources=sources, error=error,
        ), status

    def original_path(document_id):
        return Path(app.instance_path, "originals", str(document_id))

    def store_document(document):
        filename, file_type, size, content, data = document
        db = models.connection()
        db.begin()
        path = None
        try:
            document_id = models.create_document(filename, file_type, size, content, g.account)
            destination = original_path(document_id)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as original:
                path = destination
                original.write(data)
            db.commit()
        except Exception:
            db.rollback()
            if path:
                path.unlink(missing_ok=True)
            raise
        return document_id

    @app.post("/documents")
    @login_required
    def upload_document():
        uploads = [upload for upload in request.files.getlist("document") if upload.filename]
        if not 1 <= len(uploads) <= app.config["MAX_UPLOAD_FILES"]:
            flash(f"Hãy chọn từ 1 đến {app.config['MAX_UPLOAD_FILES']} tệp.", "error")
            return redirect(url_for("documents") + "#upload", code=303)

        results = []
        docx_supported = None
        for upload in uploads:
            result = {
                "filename": upload.filename,
                "file_type": Path(upload.filename).suffix.lstrip(".").upper() or "—",
                "size": None,
            }
            try:
                upload.stream.seek(0, 2)
                result["size"] = upload.stream.tell()
                upload.stream.seek(0)
                document = extract_document(upload, app.config["MAX_UPLOAD_BYTES"])
                result.update(filename=document[0], file_type=document[1].upper())
                if document[1] == "docx":
                    if docx_supported is None:
                        docx_supported = models.supports_docx()
                    if not docx_supported:
                        raise ValueError(
                            "Cơ sở dữ liệu chưa hỗ trợ DOCX. "
                            "Quản trị viên cần duyệt và import migration 002_allow_docx_only.sql."
                        )
                result["id"] = store_document(document)
            except ValueError as error:
                result["error"] = str(error)
            except (MySQLError, OSError):
                app.logger.exception("Could not save uploaded document")
                result["error"] = "Không lưu được tệp. Hãy kiểm tra kết nối và dung lượng lưu trữ."
            results.append(result)

        return render_template("documents.html", documents=models.list_documents(g.account), results=results)

    @app.get("/documents/<int:document_id>/download")
    @login_required
    def download_document(document_id):
        document = models.find_document(document_id, g.account)
        if document is None:
            abort(404)
        path = original_path(document_id)
        if path.is_file():
            return send_file(path, as_attachment=True, download_name=document["filename"])
        return send_file(
            BytesIO(document["content"].encode("utf-8")),
            mimetype="text/plain", as_attachment=True,
            download_name=f"{Path(document['filename']).stem}-noi-dung.txt",
        )

    @app.get("/summary")
    @login_required
    def summary():
        documents = models.list_documents(g.account)
        selected = request.args.get("document_id", type=int)
        return render_template(
            "summary.html", documents=documents, selected=selected,
            llm_configured=bool(app.config["LLM_API_KEY"] and app.config["LLM_MODEL"]),
        )

    @app.get("/admin")
    @login_required
    def admin():
        if g.account["role"] != "admin":
            abort(403, "Trang này chỉ dành cho quản trị viên.")
        return render_template(
            "admin.html", admins=models.list_admins(), document_count=len(models.list_documents(g.account))
        )


    @app.get("/documents/<int:document_id>")
    @login_required
    def document_detail(document_id):
        document = models.find_document(document_id, g.account)
        if document is None:
            abort(404)
        return render_template("documents.html", document=document)

    @app.post("/documents/<int:document_id>/delete")
    @login_required
    def delete_document(document_id):
        if not models.delete_document(document_id, g.account):
            abort(404)
        try:
            original_path(document_id).unlink(missing_ok=True)
        except OSError:
            app.logger.exception("Could not remove original document %s", document_id)
        flash("Đã xóa tài liệu.", "success")
        return redirect(url_for("documents"), code=303)

    return app

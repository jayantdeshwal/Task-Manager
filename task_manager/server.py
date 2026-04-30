import json
import mimetypes
import os
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from task_manager.auth import SESSION_COOKIE, create_session_token, read_session_token
from task_manager.database import BASE_DIR, init_db
from task_manager.repository import (
    AppError,
    create_project,
    create_task,
    dashboard,
    get_user,
    list_projects,
    list_tasks,
    list_users,
    login,
    signup,
    update_project_members,
    update_task,
)


PUBLIC_DIR = BASE_DIR / "public"


class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.dispatch()

    def do_POST(self):
        self.dispatch()

    def do_PATCH(self):
        self.dispatch()

    def log_message(self, format, *args):
        return

    def dispatch(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path.startswith("/api/"):
                self.handle_api(path)
            else:
                self.serve_static(path)
        except AppError as exc:
            self.json_response({"error": exc.message}, exc.status)
        except Exception as exc:
            self.json_response({"error": "Something went wrong", "detail": str(exc)}, 500)

    def read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode())
        except json.JSONDecodeError as exc:
            raise AppError("Request body must be valid JSON") from exc

    def current_user(self):
        cookie_header = self.headers.get("Cookie", "")
        jar = cookies.SimpleCookie(cookie_header)
        morsel = jar.get(SESSION_COOKIE)
        payload = read_session_token(morsel.value if morsel else None)
        if not payload:
            raise AppError("Authentication required", 401)
        user = get_user(payload["user_id"])
        if not user:
            raise AppError("Authentication required", 401)
        return user

    def handle_api(self, path):
        method = self.command
        data = self.read_json() if method in {"POST", "PATCH"} else {}

        if method == "POST" and path == "/api/auth/signup":
            user = signup(data)
            return self.set_session(user)
        if method == "POST" and path == "/api/auth/login":
            user = login(data)
            return self.set_session(user)
        if method == "POST" and path == "/api/auth/logout":
            return self.clear_session()

        user = self.current_user()
        if method == "GET" and path == "/api/auth/me":
            return self.json_response({"user": user})
        if method == "GET" and path == "/api/users":
            return self.json_response({"users": list_users(user)})
        if method == "GET" and path == "/api/projects":
            return self.json_response({"projects": list_projects(user)})
        if method == "POST" and path == "/api/projects":
            return self.json_response({"project": create_project(data, user)}, 201)
        if method == "PATCH" and path.startswith("/api/projects/") and path.endswith("/members"):
            project_id = int(path.split("/")[3])
            return self.json_response({"project": update_project_members(project_id, data, user)})
        if method == "GET" and path == "/api/tasks":
            return self.json_response({"tasks": list_tasks(user)})
        if method == "POST" and path == "/api/tasks":
            return self.json_response({"task": create_task(data, user)}, 201)
        if method == "PATCH" and path.startswith("/api/tasks/"):
            task_id = int(path.rsplit("/", 1)[1])
            return self.json_response({"task": update_task(task_id, data, user)})
        if method == "GET" and path == "/api/dashboard":
            return self.json_response(dashboard(user))

        raise AppError("Route not found", 404)

    def set_session(self, user):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header(
            "Set-Cookie",
            f"{SESSION_COOKIE}={create_session_token(user['id'])}; HttpOnly; SameSite=Lax; Path=/; Max-Age=604800",
        )
        self.end_headers()
        self.wfile.write(json.dumps({"user": user}).encode())

    def clear_session(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Set-Cookie", f"{SESSION_COOKIE}=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True}).encode())

    def json_response(self, payload, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def serve_static(self, path):
        target = "index.html" if path in {"", "/"} else path.lstrip("/")
        file_path = (PUBLIC_DIR / target).resolve()
        if PUBLIC_DIR.resolve() not in file_path.parents and file_path != PUBLIC_DIR.resolve():
            raise AppError("Not found", 404)
        if not file_path.exists() or file_path.is_dir():
            file_path = PUBLIC_DIR / "index.html"
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(file_path.read_bytes())


def run():
    init_db()
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), RequestHandler)
    print(f"Team Task Manager running on http://localhost:{port}")
    server.serve_forever()

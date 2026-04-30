from datetime import date

from task_manager.auth import hash_password, verify_password
from task_manager.database import get_connection


VALID_ROLES = {"admin", "member"}
VALID_STATUSES = {"todo", "in_progress", "done"}


class AppError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def row_to_dict(row):
    return dict(row) if row else None


def public_user(row):
    user = row_to_dict(row)
    if user:
        user.pop("password_hash", None)
    return user


def require_text(data, field, min_length=1, max_length=120):
    value = str(data.get(field, "")).strip()
    if len(value) < min_length:
        raise AppError(f"{field.replace('_', ' ').title()} is required")
    if len(value) > max_length:
        raise AppError(f"{field.replace('_', ' ').title()} must be {max_length} characters or fewer")
    return value


def optional_text(data, field, max_length=500):
    value = str(data.get(field, "")).strip()
    if len(value) > max_length:
        raise AppError(f"{field.replace('_', ' ').title()} must be {max_length} characters or fewer")
    return value


def parse_due_date(value):
    if not value:
        return None
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise AppError("Due date must use YYYY-MM-DD format") from exc
    return value


def signup(data):
    name = require_text(data, "name", max_length=80)
    email = require_text(data, "email", max_length=120).lower()
    password = str(data.get("password", ""))
    role = str(data.get("role", "member")).lower()
    if "@" not in email or "." not in email:
        raise AppError("A valid email is required")
    if len(password) < 6:
        raise AppError("Password must be at least 6 characters")
    if role not in VALID_ROLES:
        raise AppError("Role must be admin or member")
    with get_connection() as db:
        try:
            cursor = db.execute(
                "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                (name, email, hash_password(password), role),
            )
        except Exception as exc:
            if "UNIQUE" in str(exc):
                raise AppError("Email is already registered", 409) from exc
            raise
        user_id = cursor.lastrowid
    return get_user(user_id)


def login(data):
    email = require_text(data, "email", max_length=120).lower()
    password = str(data.get("password", ""))
    with get_connection() as db:
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not user or not verify_password(password, user["password_hash"]):
        raise AppError("Invalid email or password", 401)
    return public_user(user)


def get_user(user_id):
    with get_connection() as db:
        user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return public_user(user)


def list_users(current_user):
    if current_user["role"] != "admin":
        raise AppError("Only admins can view all users", 403)
    with get_connection() as db:
        rows = db.execute("SELECT id, name, email, role, created_at FROM users ORDER BY name").fetchall()
    return [row_to_dict(row) for row in rows]


def create_project(data, current_user):
    if current_user["role"] != "admin":
        raise AppError("Only admins can create projects", 403)
    name = require_text(data, "name", max_length=120)
    description = optional_text(data, "description")
    member_ids = [int(user_id) for user_id in data.get("member_ids", []) if str(user_id).isdigit()]
    if current_user["id"] not in member_ids:
        member_ids.append(current_user["id"])
    with get_connection() as db:
        cursor = db.execute(
            "INSERT INTO projects (name, description, created_by) VALUES (?, ?, ?)",
            (name, description, current_user["id"]),
        )
        project_id = cursor.lastrowid
        for user_id in member_ids:
            db.execute(
                "INSERT OR IGNORE INTO project_members (project_id, user_id) VALUES (?, ?)",
                (project_id, user_id),
            )
    return get_project(project_id, current_user)


def can_access_project(db, project_id, user):
    if user["role"] == "admin":
        return True
    member = db.execute(
        "SELECT 1 FROM project_members WHERE project_id = ? AND user_id = ?",
        (project_id, user["id"]),
    ).fetchone()
    return member is not None


def get_project(project_id, current_user):
    with get_connection() as db:
        if not can_access_project(db, project_id, current_user):
            raise AppError("Project not found", 404)
        project = db.execute(
            """
            SELECT p.*, u.name AS owner_name
            FROM projects p
            JOIN users u ON u.id = p.created_by
            WHERE p.id = ?
            """,
            (project_id,),
        ).fetchone()
        if not project:
            raise AppError("Project not found", 404)
        members = db.execute(
            """
            SELECT u.id, u.name, u.email, u.role
            FROM users u
            JOIN project_members pm ON pm.user_id = u.id
            WHERE pm.project_id = ?
            ORDER BY u.name
            """,
            (project_id,),
        ).fetchall()
    result = row_to_dict(project)
    result["members"] = [row_to_dict(member) for member in members]
    return result


def list_projects(current_user):
    with get_connection() as db:
        if current_user["role"] == "admin":
            rows = db.execute(
                """
                SELECT p.*, COUNT(DISTINCT t.id) AS task_count, GROUP_CONCAT(DISTINCT pm.user_id) AS member_ids
                FROM projects p
                LEFT JOIN tasks t ON t.project_id = p.id
                LEFT JOIN project_members pm ON pm.project_id = p.id
                GROUP BY p.id
                ORDER BY p.created_at DESC
                """
            ).fetchall()
        else:
            rows = db.execute(
                """
                SELECT p.*, COUNT(DISTINCT t.id) AS task_count, GROUP_CONCAT(DISTINCT all_pm.user_id) AS member_ids
                FROM projects p
                JOIN project_members pm ON pm.project_id = p.id AND pm.user_id = ?
                LEFT JOIN tasks t ON t.project_id = p.id
                LEFT JOIN project_members all_pm ON all_pm.project_id = p.id
                GROUP BY p.id
                ORDER BY p.created_at DESC
                """,
                (current_user["id"],),
            ).fetchall()
    projects = []
    for row in rows:
        project = row_to_dict(row)
        project["member_ids"] = [
            int(user_id) for user_id in (project.pop("member_ids") or "").split(",") if user_id
        ]
        projects.append(project)
    return projects


def update_project_members(project_id, data, current_user):
    if current_user["role"] != "admin":
        raise AppError("Only admins can manage project members", 403)
    member_ids = [int(user_id) for user_id in data.get("member_ids", []) if str(user_id).isdigit()]
    if current_user["id"] not in member_ids:
        member_ids.append(current_user["id"])
    with get_connection() as db:
        exists = db.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not exists:
            raise AppError("Project not found", 404)
        db.execute("DELETE FROM project_members WHERE project_id = ?", (project_id,))
        for user_id in member_ids:
            db.execute(
                "INSERT OR IGNORE INTO project_members (project_id, user_id) VALUES (?, ?)",
                (project_id, user_id),
            )
    return get_project(project_id, current_user)


def create_task(data, current_user):
    if current_user["role"] != "admin":
        raise AppError("Only admins can create tasks", 403)
    project_id = int(data.get("project_id") or 0)
    title = require_text(data, "title", max_length=120)
    description = optional_text(data, "description")
    status = str(data.get("status", "todo"))
    due_date = parse_due_date(data.get("due_date"))
    assigned_to = data.get("assigned_to") or None
    assigned_to = int(assigned_to) if assigned_to else None
    if status not in VALID_STATUSES:
        raise AppError("Status must be todo, in_progress, or done")
    with get_connection() as db:
        if not can_access_project(db, project_id, current_user):
            raise AppError("Project not found", 404)
        if assigned_to:
            member = db.execute(
                "SELECT 1 FROM project_members WHERE project_id = ? AND user_id = ?",
                (project_id, assigned_to),
            ).fetchone()
            if not member:
                raise AppError("Assigned user must be a project member")
        cursor = db.execute(
            """
            INSERT INTO tasks (project_id, title, description, assigned_to, status, due_date, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (project_id, title, description, assigned_to, status, due_date, current_user["id"]),
        )
        task_id = cursor.lastrowid
    return get_task(task_id, current_user)


def get_task(task_id, current_user):
    with get_connection() as db:
        task = db.execute(
            """
            SELECT t.*, p.name AS project_name, u.name AS assignee_name
            FROM tasks t
            JOIN projects p ON p.id = t.project_id
            LEFT JOIN users u ON u.id = t.assigned_to
            WHERE t.id = ?
            """,
            (task_id,),
        ).fetchone()
        if not task or not can_access_project(db, task["project_id"], current_user):
            raise AppError("Task not found", 404)
    return row_to_dict(task)


def list_tasks(current_user):
    with get_connection() as db:
        if current_user["role"] == "admin":
            rows = db.execute(task_query() + " ORDER BY t.created_at DESC").fetchall()
        else:
            rows = db.execute(
                task_query()
                + """
                JOIN project_members pm ON pm.project_id = t.project_id AND pm.user_id = ?
                WHERE t.assigned_to = ? OR pm.user_id = ?
                ORDER BY t.created_at DESC
                """,
                (current_user["id"], current_user["id"], current_user["id"]),
            ).fetchall()
    return [row_to_dict(row) for row in rows]


def task_query():
    return """
        SELECT t.*, p.name AS project_name, u.name AS assignee_name
        FROM tasks t
        JOIN projects p ON p.id = t.project_id
        LEFT JOIN users u ON u.id = t.assigned_to
    """


def update_task(task_id, data, current_user):
    task = get_task(task_id, current_user)
    status = str(data.get("status", task["status"]))
    if status not in VALID_STATUSES:
        raise AppError("Status must be todo, in_progress, or done")
    if current_user["role"] != "admin" and task["assigned_to"] != current_user["id"]:
        raise AppError("Members can update only their assigned tasks", 403)
    fields = {"status": status}
    if current_user["role"] == "admin":
        fields["title"] = require_text(data, "title", max_length=120) if "title" in data else task["title"]
        fields["description"] = optional_text(data, "description") if "description" in data else task["description"]
        fields["due_date"] = parse_due_date(data.get("due_date")) if "due_date" in data else task["due_date"]
        if "assigned_to" in data:
            assigned_to = data.get("assigned_to") or None
            fields["assigned_to"] = int(assigned_to) if assigned_to else None
    with get_connection() as db:
        assigned_to = fields.get("assigned_to", task["assigned_to"])
        if assigned_to:
            member = db.execute(
                "SELECT 1 FROM project_members WHERE project_id = ? AND user_id = ?",
                (task["project_id"], assigned_to),
            ).fetchone()
            if not member:
                raise AppError("Assigned user must be a project member")
        db.execute(
            """
            UPDATE tasks
            SET title = ?, description = ?, assigned_to = ?, status = ?, due_date = ?
            WHERE id = ?
            """,
            (
                fields.get("title", task["title"]),
                fields.get("description", task["description"]),
                fields.get("assigned_to", task["assigned_to"]),
                fields["status"],
                fields.get("due_date", task["due_date"]),
                task_id,
            ),
        )
    return get_task(task_id, current_user)


def dashboard(current_user):
    tasks = list_tasks(current_user)
    today = date.today().isoformat()
    totals = {
        "total": len(tasks),
        "todo": 0,
        "in_progress": 0,
        "done": 0,
        "overdue": 0,
    }
    for task in tasks:
        totals[task["status"]] += 1
        if task["due_date"] and task["due_date"] < today and task["status"] != "done":
            totals["overdue"] += 1
    return {"stats": totals, "recent_tasks": tasks[:5]}

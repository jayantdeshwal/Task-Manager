# Team Task Manager

A full-stack web application for managing team projects, assigning tasks, and tracking progress with role-based access for Admin and Member users.

This project is intentionally simple and assignment-focused. It includes the required authentication, project/team management, task assignment, status tracking, dashboard metrics, REST APIs, database relationships, validations, and Railway deployment setup.

## Live Deployment

Deploy this repository on Railway and add the deployed URL here:

```text
Live URL: <your-railway-url>
```

## Features

- User signup and login
- Admin and Member roles
- Admin project creation
- Admin team member selection for each project
- Admin task creation and assignment
- Task status tracking: `todo`, `in_progress`, `done`
- Member access to assigned/team project work
- Dashboard summary for total tasks, status counts, and overdue tasks
- REST API backend
- SQLite database with proper table relationships
- Server-side validation and role-based access control

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | HTML, CSS, Vanilla JavaScript |
| Backend | Python HTTP server |
| Database | SQLite |
| Authentication | Signed HTTP-only session cookie |
| Deployment | Railway |

No external Python packages are required.

## Project Structure

```text
EtharaAI/
+-- app.py
+-- Procfile
+-- README.md
+-- requirements.txt
+-- runtime.txt
+-- public/
|   +-- index.html
|   +-- styles.css
|   +-- app.js
+-- task_manager/
    +-- __init__.py
    +-- auth.py
    +-- database.py
    +-- repository.py
    +-- server.py
```

## Architecture

The app uses a simple three-part architecture:

1. The browser loads static files from `public/`.
2. The frontend calls REST endpoints under `/api/...`.
3. The backend validates the request, checks the logged-in user's role, and reads/writes SQLite data.

```text
Browser UI
   |
   | fetch('/api/...')
   v
Python HTTP Server
   |
   | repository functions
   v
SQLite Database
```

## Main Application Flow

1. A user signs up or logs in.
2. The server creates a signed HTTP-only session cookie.
3. The frontend requests `/api/auth/me` to identify the current user.
4. Admin users can create projects, select team members, and create tasks.
5. Member users can view accessible projects/tasks and update assigned task status.
6. The dashboard summarizes task progress and overdue work.

## Roles and Permissions

| Action | Admin | Member |
| --- | --- | --- |
| Signup/Login | Yes | Yes |
| View dashboard | Yes | Yes |
| View accessible projects | Yes | Yes |
| Create projects | Yes | No |
| Manage project members | Yes | No |
| Create tasks | Yes | No |
| Assign tasks | Yes | No |
| Update any task status | Yes | No |
| Update assigned task status | Yes | Yes |

## Database Design

The app uses four related tables:

### `users`

Stores registered users.

Important fields:

- `id`
- `name`
- `email`
- `password_hash`
- `role`

### `projects`

Stores project records created by admins.

Important fields:

- `id`
- `name`
- `description`
- `created_by`

### `project_members`

Connects users to projects.

Important fields:

- `project_id`
- `user_id`

### `tasks`

Stores task details and assignment.

Important fields:

- `id`
- `project_id`
- `title`
- `description`
- `assigned_to`
- `status`
- `due_date`
- `created_by`

## REST API Overview

| Method | Endpoint | Purpose | Access |
| --- | --- | --- | --- |
| `POST` | `/api/auth/signup` | Create account | Public |
| `POST` | `/api/auth/login` | Login | Public |
| `POST` | `/api/auth/logout` | Logout | Authenticated |
| `GET` | `/api/auth/me` | Get current user | Authenticated |
| `GET` | `/api/users` | List users for assignment | Admin |
| `GET` | `/api/projects` | List accessible projects | Authenticated |
| `POST` | `/api/projects` | Create project | Admin |
| `PATCH` | `/api/projects/:id/members` | Update project members | Admin |
| `GET` | `/api/tasks` | List accessible tasks | Authenticated |
| `POST` | `/api/tasks` | Create task | Admin |
| `PATCH` | `/api/tasks/:id` | Update task status/details | Admin or assigned member |
| `GET` | `/api/dashboard` | Dashboard statistics | Authenticated |

## Validations

The backend validates:

- Required name, email, password, project name, and task title
- Email uniqueness
- Minimum password length
- Allowed roles: `admin`, `member`
- Allowed task statuses: `todo`, `in_progress`, `done`
- Due date format: `YYYY-MM-DD`
- Task assignee must belong to the selected project
- Members can update only tasks assigned to them

## Run Locally

Use Python 3.12 or newer.

```bash
python app.py
```

Open the app:

```text
http://localhost:8000
```

The app creates a local SQLite database automatically at:

```text
data/task_manager.db
```

This file is ignored by Git.

## Railway Deployment

1. Push this repository to GitHub.
2. Create a new Railway project.
3. Select this GitHub repository.
4. Add this environment variable:

```text
SECRET_KEY=<any-long-random-secret>
```

Optional Railway database path:

```text
DATABASE_PATH=/app/data/task_manager.db
```

Railway will use the `Procfile`:

```text
web: python app.py
```

The app automatically reads Railway's `PORT` environment variable.

## Notes for Reviewers

- The application keeps the scope limited to the assignment requirements.
- The backend is dependency-free to make deployment simple.
- Role-based access control is enforced on the server, not only in the UI.
- The database schema uses foreign keys for user, project, membership, and task relationships.

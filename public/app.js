const state = {
  authMode: "login",
  page: "dashboard",
  user: null,
  users: [],
  projects: [],
  tasks: [],
};

const pageCopy = {
  dashboard: {
    title: "Dashboard",
    subtitle: "Track progress, status, and overdue work at a glance.",
  },
  projects: {
    title: "Projects",
    subtitle: "Create projects and manage the team members attached to them.",
  },
  tasks: {
    title: "Tasks",
    subtitle: "Create, assign, and update work across your projects.",
  },
};

const $ = (selector) => document.querySelector(selector);
const today = new Date().toISOString().slice(0, 10);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    ...options,
  });
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.error || "Request failed");
  }
  return body;
}

function showMessage(message, target = "#appMessage") {
  const element = $(target);
  element.textContent = message;
  element.classList.remove("hidden");
  window.setTimeout(() => element.classList.add("hidden"), 2800);
}

function setAuthMode(mode) {
  state.authMode = mode;
  document.querySelectorAll("[data-auth-mode]").forEach((button) => {
    button.classList.toggle("active", button.dataset.authMode === mode);
  });
  document.querySelectorAll(".signup-only").forEach((element) => {
    element.classList.toggle("hidden", mode !== "signup");
  });
  $("#authMessage").textContent = "";
}

function setPage(page) {
  state.page = page;
  const copy = pageCopy[page];
  $("#pageTitle").textContent = copy.title;
  $("#pageSubtitle").textContent = copy.subtitle;

  document.querySelectorAll("[data-page]").forEach((button) => {
    button.classList.toggle("active", button.dataset.page === page);
  });
  document.querySelectorAll(".page").forEach((section) => {
    section.classList.toggle("active-page", section.id === `${page}Page`);
  });
}

async function loadMe() {
  try {
    const { user } = await api("/api/auth/me");
    state.user = user;
    $("#authView").classList.add("hidden");
    $("#appView").classList.remove("hidden");
    await loadData();
  } catch {
    $("#authView").classList.remove("hidden");
    $("#appView").classList.add("hidden");
  }
}

async function loadData() {
  const requests = [api("/api/dashboard"), api("/api/projects"), api("/api/tasks")];
  if (state.user.role === "admin") {
    requests.push(api("/api/users"));
  }
  const [dashboard, projects, tasks, users] = await Promise.all(requests);
  state.projects = projects.projects;
  state.tasks = tasks.tasks;
  state.users = users ? users.users : [];
  renderDashboard(dashboard.stats);
  renderProjects();
  renderTasks();
  renderAdminTools();
  setPage(state.page);
}

function renderDashboard(stats) {
  $("#currentUser").textContent = `${state.user.name} / ${state.user.role}`;
  $("#statTotal").textContent = stats.total;
  $("#statTodo").textContent = stats.todo;
  $("#statProgress").textContent = stats.in_progress;
  $("#statOverdue").textContent = stats.overdue;
  renderRecentTasks();
}

function renderRecentTasks() {
  const recentTasks = state.tasks.slice(0, 5);
  if (!recentTasks.length) {
    $("#recentTaskList").innerHTML = `<p class="empty">No recent tasks yet.</p>`;
    return;
  }
  $("#recentTaskList").innerHTML = recentTasks.map(taskCard).join("");
}

function renderAdminTools() {
  const admin = state.user.role === "admin";
  document.querySelectorAll(".admin-only").forEach((element) => {
    element.classList.toggle("hidden", !admin);
  });
  if (!admin) return;

  const userOptions = state.users
    .map((user) => `<option value="${user.id}">${escapeHtml(user.name)} - ${escapeHtml(user.role)}</option>`)
    .join("");
  $("#projectMembers").innerHTML = userOptions;

  $("#taskProject").innerHTML = state.projects
    .map((project) => `<option value="${project.id}">${escapeHtml(project.name)}</option>`)
    .join("");
  renderAssigneeOptions();
}

function renderAssigneeOptions() {
  const projectId = Number($("#taskProject").value);
  const project = state.projects.find((item) => item.id === projectId);
  const allowedIds = new Set((project?.member_ids || []).map(Number));
  const users = state.users.filter((user) => allowedIds.has(user.id));
  $("#taskAssignee").innerHTML =
    `<option value="">Unassigned</option>` +
    users.map((user) => `<option value="${user.id}">${escapeHtml(user.name)}</option>`).join("");
}

function renderProjects() {
  $("#projectCount").textContent = state.projects.length;
  if (!state.projects.length) {
    $("#projectList").innerHTML = `<p class="empty">No projects yet.</p>`;
    return;
  }
  $("#projectList").innerHTML = state.projects
    .map(
      (project) => `
        <article class="item">
          <div class="section-title">
            <h3>${escapeHtml(project.name)}</h3>
            <span class="count-pill">${project.task_count || 0} tasks</span>
          </div>
          <p class="meta">${escapeHtml(project.description || "No description")}</p>
        </article>
      `,
    )
    .join("");
}

function renderTasks() {
  $("#taskCount").textContent = state.tasks.length;
  if (!state.tasks.length) {
    $("#taskList").innerHTML = `<p class="empty">No tasks to show.</p>`;
    return;
  }
  $("#taskList").innerHTML = state.tasks.map((task) => taskCard(task, true)).join("");

  document.querySelectorAll("[data-status-task]").forEach((select) => {
    select.addEventListener("change", async (event) => {
      await updateTaskStatus(event.target.dataset.statusTask, event.target.value);
    });
  });
}

function taskCard(task, withControls = false) {
  const overdue = task.due_date && task.due_date < today && task.status !== "done";
  return `
    <article class="item">
      <div class="section-title">
        <h3>${escapeHtml(task.title)}</h3>
        <span class="badge ${task.status}">${task.status.replace("_", " ")}</span>
      </div>
      <p class="meta">${escapeHtml(task.description || "No description")}</p>
      <p class="meta">Project: ${escapeHtml(task.project_name)} | Assigned: ${escapeHtml(task.assignee_name || "Unassigned")}</p>
      <div class="task-footer">
        <span class="meta ${overdue ? "overdue" : ""}">Due: ${task.due_date || "No date"}</span>
        ${withControls ? statusControl(task) : ""}
      </div>
    </article>
  `;
}

function statusControl(task) {
  const canUpdate = state.user.role === "admin" || task.assigned_to === state.user.id;
  if (!canUpdate) return "";
  return `
    <select data-status-task="${task.id}" aria-label="Update task status">
      ${["todo", "in_progress", "done"]
        .map((status) => `<option value="${status}" ${task.status === status ? "selected" : ""}>${status.replace("_", " ")}</option>`)
        .join("")}
    </select>
  `;
}

async function updateTaskStatus(taskId, status) {
  try {
    await api(`/api/tasks/${taskId}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
    await loadData();
    showMessage("Task status updated");
  } catch (error) {
    showMessage(error.message);
  }
}

function formData(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function selectedNumbers(select) {
  return Array.from(select.selectedOptions).map((option) => Number(option.value));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

document.querySelectorAll("[data-auth-mode]").forEach((button) => {
  button.addEventListener("click", () => setAuthMode(button.dataset.authMode));
});

document.querySelectorAll("[data-page]").forEach((button) => {
  button.addEventListener("click", () => setPage(button.dataset.page));
});

$("#authForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = formData(form);
  const path = state.authMode === "signup" ? "/api/auth/signup" : "/api/auth/login";
  try {
    await api(path, { method: "POST", body: JSON.stringify(data) });
    form.reset();
    await loadMe();
  } catch (error) {
    $("#authMessage").textContent = error.message;
  }
});

$("#logoutButton").addEventListener("click", async () => {
  await api("/api/auth/logout", { method: "POST", body: "{}" });
  state.user = null;
  $("#appView").classList.add("hidden");
  $("#authView").classList.remove("hidden");
});

$("#projectForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = formData(form);
  data.member_ids = selectedNumbers($("#projectMembers"));
  try {
    await api("/api/projects", { method: "POST", body: JSON.stringify(data) });
    form.reset();
    await loadData();
    setPage("projects");
    showMessage("Project created");
  } catch (error) {
    showMessage(error.message);
  }
});

$("#taskForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = formData(form);
  try {
    await api("/api/tasks", { method: "POST", body: JSON.stringify(data) });
    form.reset();
    await loadData();
    setPage("tasks");
    showMessage("Task created");
  } catch (error) {
    showMessage(error.message);
  }
});

$("#taskProject").addEventListener("change", renderAssigneeOptions);

setAuthMode("login");
setPage("dashboard");
loadMe();

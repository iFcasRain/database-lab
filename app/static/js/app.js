/* 前端公共脚本：统一调用接口、统一显示错误提示。
   页面层不拼接 SQL，只把用户输入作为 JSON 提交给后端接口。 */

async function apiRequest(path, options = {}) {
  const config = {
    method: options.method || "GET",
    headers: { Accept: "application/json" },
    credentials: "same-origin",
  };
  if (options.body !== undefined) {
    config.headers["Content-Type"] = "application/json";
    config.body = JSON.stringify(options.body);
  }

  let response;
  try {
    response = await fetch(path, config);
  } catch (error) {
    throw new Error("网络连接失败，请检查网络后重试");
  }

  let payload = null;
  try {
    payload = await response.json();
  } catch (error) {
    payload = null;
  }

  if (!response.ok || !payload || payload.success === false) {
    const message =
      (payload && payload.error && payload.error.message) || "操作失败，请稍后重试";
    const error = new Error(message);
    error.code = payload && payload.error && payload.error.code;
    error.requestId = payload && payload.request_id;
    throw error;
  }
  return payload.data;
}

function toast(message, type = "info") {
  const box = document.getElementById("toast");
  if (!box) return;
  const item = document.createElement("div");
  item.className = "item " + type;
  item.textContent = message;
  box.appendChild(item);
  requestAnimationFrame(() => item.classList.add("show"));
  setTimeout(() => {
    item.classList.remove("show");
    setTimeout(() => item.remove(), 250);
  }, 3200);
}

function showError(error) {
  let text = error.message || "操作失败";
  if (error.requestId) {
    text += "（请求号 " + error.requestId + "）";
  }
  toast(text, "error");
}

function money(value) {
  const number = Number(value || 0);
  return number.toFixed(2);
}

/* 把表单元素收集成对象，空字符串保留，交由后端统一校验。 */
function formValues(form) {
  const data = {};
  new FormData(form).forEach((value, key) => {
    data[key] = typeof value === "string" ? value.trim() : value;
  });
  return data;
}

/* 统一的“提交后刷新”流程：失败弹提示，成功弹提示并刷新页面。 */
function bindSubmit(formId, path, options = {}) {
  const form = document.getElementById(formId);
  if (!form) return;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button[type=submit]");
    if (button) button.disabled = true;
    try {
      const body = options.buildBody ? options.buildBody(form) : formValues(form);
      await apiRequest(path, { method: options.method || "POST", body });
      toast(options.successMessage || "操作成功", "success");
      if (options.reload === false) {
        if (options.onSuccess) options.onSuccess();
      } else {
        setTimeout(() => window.location.reload(), 500);
      }
    } catch (error) {
      showError(error);
    } finally {
      if (button) button.disabled = false;
    }
  });
}

function openModal(id) {
  const node = document.getElementById(id);
  if (node) node.classList.add("open");
}

function closeModal(id) {
  const node = document.getElementById(id);
  if (node) node.classList.remove("open");
}

document.addEventListener("click", (event) => {
  const target = event.target;
  if (target.matches("[data-close-modal]")) {
    const mask = target.closest(".modal-mask");
    if (mask) mask.classList.remove("open");
  }
  if (target.classList && target.classList.contains("modal-mask")) {
    target.classList.remove("open");
  }
});

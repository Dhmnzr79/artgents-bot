import { mountWidget } from "./widget/widget.js";

const notice = document.getElementById("panel-notice");
const report = text => { notice.textContent = text; };

document.getElementById("copy-launch-command").addEventListener("click", async () => {
  const command = document.getElementById("launch-command");
  try {
    await navigator.clipboard.writeText(command.textContent.trim());
    report("Команда скопирована. Вставьте её в PowerShell.");
  } catch {
    const range = document.createRange();
    range.selectNodeContents(command);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    report("Команда выделена. Нажмите Ctrl+C и вставьте в PowerShell.");
  }
});
document.getElementById("refresh-page").addEventListener("click", () => location.reload());

const state = document.getElementById("bot-state");
const label = document.getElementById("bot-state-label");
const checkedAt = document.getElementById("checked-at");
let failures = 0;
let timer;
async function checkConnection() {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 2000);
  try {
    const response = await fetch("/health/live", {cache:"no-store", signal:controller.signal});
    const payload = await response.json();
    if (!response.ok || payload.ok !== true || payload.status !== "live") throw new Error("Unavailable");
    failures = 0;
    state.dataset.state = "ready";
    label.textContent = "Бот готов";
    document.getElementById("connection-heading").textContent = "Сервер отвечает. Можно тестировать.";
  } catch {
    failures++;
    state.dataset.state = failures < 3 ? "checking" : "offline";
    label.textContent = failures < 3 ? "Проверяем связь…" : "Бот недоступен";
    document.getElementById("connection-heading").textContent = failures < 3
      ? "Возможно, идёт перезапуск. Подождите несколько секунд."
      : "Проверьте открытый терминал. Если бот остановлен — запустите команду ниже.";
  } finally {
    clearTimeout(timeout);
    checkedAt.textContent = "Проверено " + new Date().toLocaleTimeString("ru-RU");
    timer = setTimeout(checkConnection, document.hidden ? 10000 : 2500);
  }
}
window.addEventListener("pagehide", () => clearTimeout(timer));
void checkConnection();

const config = JSON.parse(document.getElementById("clinic-widget-config").textContent);
const mount = document.createElement("div");
document.body.appendChild(mount);
const widget = mountWidget(mount, config);
const launcher = mount.querySelector("[data-clinic-launcher-open], [data-clinic-launcher]");
const input = mount.querySelector("[data-clinic-input]");
const form = mount.querySelector("[data-clinic-composer-form]");
const send = mount.querySelector("[data-clinic-send]");
const openChat = () => {
  if (launcher.getAttribute("aria-expanded") !== "true") launcher.click();
};
document.getElementById("open-chat").addEventListener("click", openChat);
document.getElementById("reset-chat").addEventListener("click", () => {
  if (mount.querySelector(".clinic-shell__welcome-screen.is-leaving")) {
    report("Дождитесь завершения ответа, затем начните новую беседу.");
    return;
  }
  widget.resetSession();
  if (!mount.querySelector(".clinic-shell__welcome-screen")) {
    report("Дождитесь завершения ответа, затем начните новую беседу.");
    return;
  }
  openChat();
  report("Начата новая беседа.");
});
const library = JSON.parse(document.getElementById("test-questions").textContent);
const questionTabs = document.getElementById("question-tabs");
const questionGroups = document.getElementById("question-groups");
library.forEach((category, index) => {
  const tab = document.createElement("button");
  tab.type = "button";
  tab.id = `question-tab-${index}`;
  tab.setAttribute("role", "tab");
  tab.setAttribute("aria-controls", `question-group-${index}`);
  tab.setAttribute("aria-selected", String(index === 0));
  tab.tabIndex = index === 0 ? 0 : -1;
  tab.textContent = `${category.title} · ${category.questions.length}`;
  questionTabs.appendChild(tab);
  const group = document.createElement("div");
  group.id = `question-group-${index}`;
  group.className = "question-group";
  group.setAttribute("role", "tabpanel");
  group.setAttribute("aria-labelledby", tab.id);
  group.hidden = index !== 0;
  const list = document.createElement("div");
  list.className = "themes";
  for (const question of category.questions) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.widgetQuestion = question;
    button.textContent = question;
    list.appendChild(button);
  }
  group.appendChild(list);
  questionGroups.appendChild(group);
});

function wireTabs(tablist) {
  const tabs = [...tablist.querySelectorAll('[role="tab"]')];
  const select = selected => {
    for (const tab of tabs) {
      const active = tab === selected;
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
      document.getElementById(tab.getAttribute("aria-controls")).hidden = !active;
    }
  };
  for (const tab of tabs) {
    tab.addEventListener("click", () => select(tab));
    tab.addEventListener("keydown", event => {
      let index = tabs.indexOf(tab);
      if (event.key === "ArrowRight") index = (index + 1) % tabs.length;
      else if (event.key === "ArrowLeft") index = (index + tabs.length - 1) % tabs.length;
      else if (event.key === "Home") index = 0;
      else if (event.key === "End") index = tabs.length - 1;
      else return;
      event.preventDefault();
      select(tabs[index]);
      tabs[index].focus();
    });
  }
}
wireTabs(document.querySelector(".view-tabs"));
wireTabs(questionTabs);

for (const button of document.querySelectorAll("[data-widget-question]")) {
  button.addEventListener("click", () => {
    openChat();
    if (input.inputMode === "numeric") {
      report("Сначала завершите или отмените ввод телефона.");
      return;
    }
    if (input.value.trim() || mount.querySelector(".clinic-shell__welcome-screen.is-leaving")) {
      report("Сначала отправьте текущий вопрос или дождитесь начала ответа.");
      return;
    }
    input.value = button.dataset.widgetQuestion;
    input.dispatchEvent(new Event("input", {bubbles:true}));
    if (send.disabled) {
      input.value = "";
      input.dispatchEvent(new Event("input", {bubbles:true}));
      report("Дождитесь ответа или завершите повторную отправку.");
      return;
    }
    report("");
    form.requestSubmit(send);
  });
}

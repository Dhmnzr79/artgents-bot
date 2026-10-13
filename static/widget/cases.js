// Authored demo gallery. Buttons and photo switches never call the provider.
const DEMO_CASES = [
  {
    id: "all-on-4",
    serviceId: "all_on_4",
    document: "implantation__service__all_on_4.md",
    title: "Восстановление зубов All-on-4",
    description: "Восстановили зубной ряд на четырёх имплантах. Подобрали форму и оттенок протеза, чтобы пациент мог снова уверенно улыбаться.",
    before: "/static/clients/demo/cases/before-2.jpg",
    after: "/static/clients/demo/cases/after-2.jpg",
  },
  {
    id: "zirconia-crowns",
    serviceId: "zirconia_crowns",
    document: "prosthetics__service__zirconia_crowns.md",
    title: "Циркониевые коронки",
    description: "Восстановили форму и цвет зубов коронками из собственной лаборатории. Согласовали естественный оттенок и вернули открытой улыбке уверенность.",
    before: "/static/clients/demo/cases/before-1.jpg",
    after: "/static/clients/demo/cases/after-1.jpg",
  },
];

export function casesForClient(clientId) {
  return clientId === "demo" ? DEMO_CASES : [];
}

export function casesForMessage(clientId, message) {
  // A direction overview lists alternatives, not a selected service.
  // Keep case offers for individual services and the welcome gallery.
  if ((message.bodyParts || []).some(part =>
    part.kind === "price_card" && part.overview
    && part.price?.source_client_id === clientId)) return [];
  const services = new Set((message.bodyParts || [])
    .filter(part => part.kind === "price_card" && part.price?.source_client_id === clientId)
    .flatMap(part => part.price.rows || [])
    .filter(row => row.source_client_id === clientId)
    .map(row => row.service_id));
  const documents = new Set((message.quickReplies || [])
    .map(reply => String(reply.ref).split("#")[0]));
  return casesForClient(clientId).filter(item =>
    services.has(item.serviceId) || documents.has(item.document));
}

export function appendCaseCards(container, cases, { apiBase, resolveUrl, selection }) {
  if (!cases.length) return;
  const gallery = document.createElement("div");
  gallery.className = "clinic-case-gallery";
  const cards = [];
  for (const item of cases) {
    const card = document.createElement("section");
    card.className = "clinic-price-card clinic-case-card";
    const title = document.createElement("h3");
    title.className = "clinic-price-card__title";
    title.textContent = item.title;
    const tabs = document.createElement("div");
    tabs.className = "clinic-price-card__tabs";
    tabs.setAttribute("role", "group");
    tabs.setAttribute("aria-label", `${item.title}: до и после лечения`);
    const photo = document.createElement("img");
    photo.className = "clinic-case-card__photo";
    photo.width = 420;
    photo.height = 300;
    photo.loading = "lazy";
    photo.decoding = "async";
    photo.draggable = false;
    const frame = document.createElement("div");
    frame.className = "clinic-case-card__frame";
    frame.appendChild(photo);
    const error = document.createElement("p");
    error.className = "clinic-case-card__error";
    error.textContent = "Не удалось загрузить фото.";
    error.hidden = true;
    photo.addEventListener("error", () => { error.hidden = false; });
    photo.addEventListener("load", () => { error.hidden = true; });
    const buttons = [];
    const select = (phase) => {
      selection[item.id] = phase;
      const label = phase === "before" ? "До" : "После";
      photo.src = resolveUrl(apiBase, item[phase]);
      photo.alt = `${item.title} — ${label.toLowerCase()} лечения`;
      error.hidden = true;
      for (const button of buttons) {
        button.setAttribute("aria-pressed", String(button.dataset.phase === phase));
      }
    };
    for (const [phase, label] of [["before", "До"], ["after", "После"]]) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "clinic-price-card__tab";
      button.dataset.phase = phase;
      button.textContent = label;
      button.addEventListener("click", () => select(phase));
      buttons.push(button);
      tabs.appendChild(button);
    }
    card.append(frame, error, tabs, title);
    const description = document.createElement("p");
    description.className = "clinic-case-card__description";
    description.textContent = item.description;
    card.appendChild(description);
    select(selection[item.id] === "after" ? "after" : "before");
    cards.push(card);
    gallery.appendChild(card);
  }
  if (cases.length > 1) {
    const navigation = document.createElement("div");
    navigation.className = "clinic-case-gallery__navigation";
    const previous = document.createElement("button");
    const next = document.createElement("button");
    for (const [button, direction, label] of [
      [previous, "previous", "Предыдущий кейс"],
      [next, "next", "Следующий кейс"],
    ]) {
      button.type = "button";
      button.className = "clinic-case-card__arrow";
      button.setAttribute("aria-label", label);
      button.innerHTML = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="${direction === "previous" ? "m15 5-7 7 7 7" : "m9 5 7 7-7 7"}" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
    }
    const counter = document.createElement("span");
    counter.className = "clinic-case-gallery__counter";
    counter.setAttribute("aria-live", "polite");
    const show = (index) => {
      selection.caseIndex = Math.max(0, Math.min(cards.length - 1, index));
      cards.forEach((card, position) => { card.hidden = position !== selection.caseIndex; });
      previous.disabled = selection.caseIndex === 0;
      next.disabled = selection.caseIndex === cards.length - 1;
      counter.textContent = `${selection.caseIndex + 1} / ${cards.length}`;
    };
    previous.addEventListener("click", () => show(selection.caseIndex - 1));
    next.addEventListener("click", () => show(selection.caseIndex + 1));
    gallery.tabIndex = 0;
    gallery.setAttribute("role", "group");
    gallery.setAttribute("aria-label", "Кейсы до и после. Листайте свайпом или стрелками.");
    gallery.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      show(selection.caseIndex + (event.key === "ArrowLeft" ? -1 : 1));
    });
    let gesture = null;
    gallery.addEventListener("touchstart", (event) => {
      if (event.touches.length !== 1) { gesture = null; return; }
      gesture = { x: event.touches[0].clientX, y: event.touches[0].clientY };
    }, { passive: true });
    gallery.addEventListener("touchcancel", () => { gesture = null; }, { passive: true });
    gallery.addEventListener("touchend", (event) => {
      if (!gesture || !event.changedTouches.length) return;
      const dx = event.changedTouches[0].clientX - gesture.x;
      const dy = event.changedTouches[0].clientY - gesture.y;
      gesture = null;
      if (Math.abs(dx) < 40 || Math.abs(dx) <= Math.abs(dy)) return;
      show(selection.caseIndex + (dx < 0 ? 1 : -1));
    }, { passive: true });
    navigation.append(previous, counter, next);
    gallery.appendChild(navigation);
    show(Number.isInteger(selection.caseIndex) ? selection.caseIndex : 0);
  }
  container.appendChild(gallery);
}

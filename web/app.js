const form = document.querySelector("#trip-form");
const stage = document.querySelector("#stage");
const events = document.querySelector("#events");
const summaryTitle = document.querySelector("#summary-title");
const summary = document.querySelector("#summary");
const itinerary = document.querySelector("#itinerary");
const budget = document.querySelector("#budget");
const quotes = document.querySelector("#quotes");
const bookings = document.querySelector("#bookings");

function tripPayload(formData) {
  return {
    origin: formData.get("origin"),
    destination: formData.get("destination"),
    days: Number(formData.get("days")),
    travelers: Number(formData.get("travelers")),
    budget_cny: Number(formData.get("budget_cny")),
    interests: String(formData.get("interests") || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
    confirmed: formData.get("confirmed") === "on",
  };
}

function item(title, lines) {
  const node = document.createElement("div");
  node.className = "item";
  node.innerHTML = `<strong>${title}</strong>${lines.map((line) => `<div class="meta">${line}</div>`).join("")}`;
  return node;
}

function render(result) {
  stage.textContent = result.stage;
  summaryTitle.textContent = result.requires_confirmation ? "等待确认" : "方案完成";
  summary.textContent = result.summary;

  events.innerHTML = "";
  result.events.forEach((event) => {
    const node = document.createElement("li");
    const tags = [event.skill, event.tool].filter(Boolean).join(" / ");
    node.textContent = tags ? `${event.message} (${tags})` : event.message;
    events.appendChild(node);
  });

  itinerary.innerHTML = "";
  result.itinerary.days.forEach((day) => {
    itinerary.appendChild(item(day.title, [day.morning, day.afternoon, day.evening]));
  });

  budget.className = `budget-box ${result.budget.status === "within_budget" ? "ok" : "warn"}`;
  budget.innerHTML = `
    <strong>${result.budget.total_cny} / ${result.budget.budget_cny} CNY</strong>
    <div class="meta">${result.budget.status}</div>
    <div class="meta">${result.budget.savings_hint || "预算内，可继续确认模拟下单。"}</div>
  `;

  quotes.innerHTML = "";
  [...result.transport_options, ...result.hotel_options, ...result.attraction_options].forEach((quote) => {
    quotes.appendChild(item(quote.name, [`${quote.provider} · ${quote.price_cny} CNY`, `确认门禁：${quote.requires_confirmation ? "是" : "否"}`]));
  });

  bookings.innerHTML = "";
  if (result.bookings.length === 0) {
    bookings.appendChild(item("尚未生成订单", ["勾选确认后再次提交，只会生成 mock 订单。"]));
  } else {
    result.bookings.forEach((booking) => {
      bookings.appendChild(item(booking.id, [booking.kind, booking.status, booking.note]));
    });
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = form.querySelector("button");
  button.disabled = true;
  stage.textContent = "running";
  try {
    const response = await fetch("/api/trips/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(tripPayload(new FormData(form))),
    });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    render(await response.json());
  } catch (error) {
    summaryTitle.textContent = "请求失败";
    summary.textContent = error.message;
    stage.textContent = "error";
  } finally {
    button.disabled = false;
  }
});


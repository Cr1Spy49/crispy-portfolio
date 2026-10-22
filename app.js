/* Small, dependency-free enhancements. The HTML remains usable without this file. */
(() => {
  "use strict";
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [
    ...root.querySelectorAll(selector),
  ];
  const cards = $$(".work-card");
  const byId = new Map(cards.map((card) => [card.dataset.id, card]));
  const validFilters = new Set([
    "all",
    "scenes",
    "avatars",
    "experiments",
    "favorites",
  ]);
  const storageKey = "crispy:favorites:v1";
  const limit = 5;
  const state = { filter: "all", search: "", expanded: false };
  let favorites = new Set();
  let toastTimer;
  let searchTimer;

  try {
    const saved = JSON.parse(localStorage.getItem(storageKey) || "[]");
    if (Array.isArray(saved))
      favorites = new Set(saved.filter((id) => byId.has(id)));
  } catch {
    /* Privacy modes and corrupted storage must not break the gallery. */
  }

  function toast(message) {
    const element = $("#toast");
    element.textContent = message;
    element.classList.add("visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => element.classList.remove("visible"), 3000);
  }

  function updateURL(updates) {
    const url = new URL(location.href);
    Object.entries(updates).forEach(([key, value]) => {
      if (value) url.searchParams.set(key, value);
      else url.searchParams.delete(key);
    });
    try {
      history.replaceState(null, "", url);
    } catch {
      /* Also usable via file://. */
    }
  }

  function normalize(value) {
    return value.toLocaleLowerCase("ru").replaceAll("ё", "е").trim();
  }

  function filteredCards() {
    const query = normalize(state.search);
    return cards.filter((card) => {
      const category =
        state.filter === "all" ||
        (state.filter === "favorites"
          ? favorites.has(card.dataset.id)
          : card.dataset.group === state.filter);
      return category && normalize(card.dataset.title).includes(query);
    });
  }

  function renderGallery({ syncURL = true } = {}) {
    const matches = filteredCards();
    const shortSelection =
      state.filter === "all" && !state.search && !state.expanded;
    const visible = new Set(shortSelection ? matches.slice(0, limit) : matches);
    cards.forEach((card) => {
      card.hidden = !visible.has(card);
    });
    $$(".filter-pill").forEach((button) => {
      const active = button.dataset.filter === state.filter;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    $("#gallery").classList.toggle(
      "is-filtered",
      state.filter !== "all" || Boolean(state.search),
    );
    $("#empty-state").hidden = matches.length > 0;
    $("#empty-message").textContent =
      state.filter === "favorites" && !favorites.size
        ? "Нажмите на сердечко у понравившейся работы — она появится здесь."
        : "Попробуйте другое название или категорию.";
    $("#gallery-count").textContent =
      `Показано ${visible.size} из ${matches.length} работ`;
    $("#gallery-status").textContent = matches.length
      ? `Найдено работ: ${matches.length}. Показано: ${visible.size}.`
      : "Работы не найдены.";
    const more = $("#show-more");
    more.hidden =
      state.filter !== "all" ||
      Boolean(state.search) ||
      matches.length <= limit;
    more.setAttribute("aria-expanded", String(state.expanded));
    more.firstChild.textContent = state.expanded
      ? "Свернуть подборку "
      : "Больше историй ";
    $("span", more).textContent =
      `${state.expanded ? "−" : "+"}${Math.max(0, matches.length - limit)}`;
    if (syncURL)
      updateURL({
        filter: state.filter === "all" ? "" : state.filter,
        q: state.search,
      });
  }

  function syncFavorites() {
    $$("[data-favorite]").forEach((button) => {
      const active = favorites.has(button.dataset.favorite);
      button.setAttribute("aria-pressed", String(active));
      const title = byId.get(button.dataset.favorite).dataset.title;
      button.setAttribute(
        "aria-label",
        `${active ? "Убрать из избранного" : "В избранное"}: ${title}`,
      );
    });
    $("#favorites-count").textContent = favorites.size;
    if (currentCard) {
      const active = favorites.has(currentCard.dataset.id);
      $("#lb-favorite").setAttribute("aria-pressed", String(active));
      $("#lb-favorite").setAttribute(
        "aria-label",
        active ? "Убрать работу из избранного" : "Добавить работу в избранное",
      );
    }
  }

  function toggleFavorite(id) {
    favorites.has(id) ? favorites.delete(id) : favorites.add(id);
    let stored = true;
    try {
      localStorage.setItem(storageKey, JSON.stringify([...favorites]));
    } catch {
      stored = false;
    }
    syncFavorites();
    if (state.filter === "favorites") {
      const focusedCard = document.activeElement.closest(".work-card");
      renderGallery();
      if (focusedCard?.hidden)
        $(".filter-pill.active").focus({ preventScroll: true });
    }
    toast(
      stored
        ? favorites.has(id)
          ? "Работа в избранном. Сохранили на этом устройстве."
          : "Работа убрана из избранного."
        : "Избранное доступно до закрытия страницы: хранилище браузера недоступно.",
    );
  }

  $$(".filter-pill").forEach((button) =>
    button.addEventListener("click", () => {
      clearTimeout(searchTimer);
      state.search = $("#work-search").value.trim();
      state.filter = button.dataset.filter;
      state.expanded = false;
      renderGallery();
    }),
  );
  $("#work-search").addEventListener("input", (event) => {
    clearTimeout(searchTimer);
    state.search = event.target.value.trim();
    searchTimer = setTimeout(() => renderGallery(), 120);
  });
  $("#reset-filters").addEventListener("click", () => {
    clearTimeout(searchTimer);
    Object.assign(state, { filter: "all", search: "", expanded: false });
    $("#work-search").value = "";
    renderGallery();
    $('.filter-pill[data-filter="all"]').focus();
  });
  $("#show-more").addEventListener("click", () => {
    state.expanded = !state.expanded;
    renderGallery();
  });
  $$("[data-favorite]").forEach((button) =>
    button.addEventListener("click", () =>
      toggleFavorite(button.dataset.favorite),
    ),
  );
  window.addEventListener("storage", (event) => {
    if (event.key !== storageKey && event.key !== null) return;
    try {
      const saved = JSON.parse(event.newValue || "[]");
      favorites = new Set(
        Array.isArray(saved) ? saved.filter((id) => byId.has(id)) : [],
      );
      syncFavorites();
      if (state.filter === "favorites") renderGallery();
    } catch {
      /* Ignore malformed data from another tab. */
    }
  });

  // Native dialog supplies focus trapping, Escape, and an inert background.
  const dialog = $("#lightbox");
  const image = $("#lb-img");
  const imageWrap = $("#lb-image-wrap");
  let currentCard = null;
  let modalCards = [];
  let returnFocus = null;
  let touchStart = null;

  function setZoom(enabled) {
    imageWrap.classList.toggle("zoomed", enabled);
    $("#lb-zoom").setAttribute("aria-pressed", String(enabled));
    $("#lb-zoom").setAttribute(
      "aria-label",
      enabled ? "Уменьшить изображение" : "Увеличить изображение",
    );
    imageWrap.scrollTo(0, 0);
  }

  function showCard(card) {
    currentCard = card;
    const { id, title, original } = card.dataset;
    setZoom(false);
    $("#lb-share").setAttribute("aria-label", "Скопировать ссылку на работу");
    $(".lightbox-hint").textContent =
      "← → для навигации · Esc — закрыть · свайп на телефоне";
    image.src = `assets/images/${id}-1600.webp`;
    image.alt = title;
    image.width = Number($("img", card).getAttribute("width"));
    image.height = Number($("img", card).getAttribute("height"));
    $("#lb-title").textContent = title;
    $("#lb-category").textContent = $(".work-category", card).textContent;
    $("#lb-counter").textContent =
      `${modalCards.indexOf(card) + 1} / ${modalCards.length}`;
    $("#lb-original").href = original;
    syncFavorites();
    updateURL({ work: id });
  }

  function openLightbox(id, trigger = null) {
    const card = byId.get(id);
    if (!card || typeof dialog.showModal !== "function") return false;
    returnFocus = trigger;
    const matches = filteredCards();
    modalCards = matches.includes(card) ? matches : cards;
    showCard(card);
    if (!dialog.open) dialog.showModal();
    document.body.classList.add("modal-open");
    return true;
  }

  function navigate(direction) {
    const index = modalCards.indexOf(currentCard);
    showCard(
      modalCards[(index + direction + modalCards.length) % modalCards.length],
    );
  }

  $$("[data-open], [data-featured]").forEach((link) =>
    link.addEventListener("click", (event) => {
      if (
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey ||
        event.button !== 0
      )
        return;
      if (openLightbox(link.dataset.open || link.dataset.featured, link))
        event.preventDefault();
    }),
  );
  $("#lb-close").addEventListener("click", () => dialog.close());
  $("#lb-prev").addEventListener("click", () => navigate(-1));
  $("#lb-next").addEventListener("click", () => navigate(1));
  $("#lb-zoom").addEventListener("click", () =>
    setZoom(!imageWrap.classList.contains("zoomed")),
  );
  $("#lb-favorite").addEventListener("click", () =>
    toggleFavorite(currentCard.dataset.id),
  );
  $("#lb-share").addEventListener("click", async () => {
    const button = $("#lb-share");
    try {
      await navigator.clipboard.writeText(location.href);
      button.setAttribute("aria-label", "Ссылка скопирована");
      $(".lightbox-hint").textContent = "Ссылка на эту работу скопирована.";
    } catch {
      $(".lightbox-hint").textContent =
        "Скопируйте адрес из строки браузера — в нём уже есть ссылка на эту работу.";
    }
  });
  dialog.addEventListener("keydown", (event) => {
    if (event.key === "Tab") {
      const controls = $$("button:not(:disabled), a[href]", dialog).filter(
        (element) => element.getClientRects().length,
      );
      const first = controls[0];
      const last = controls.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      event.preventDefault();
      navigate(event.key === "ArrowRight" ? 1 : -1);
    }
  });
  dialog.addEventListener("click", (event) => {
    if (event.target !== dialog) return;
    const { left, top, right, bottom } = dialog.getBoundingClientRect();
    if (
      event.clientX < left ||
      event.clientX > right ||
      event.clientY < top ||
      event.clientY > bottom
    )
      dialog.close();
  });
  dialog.addEventListener("close", () => {
    document.body.classList.remove("modal-open");
    updateURL({ work: "" });
    image.removeAttribute("src");
    currentCard = null;
    if (returnFocus && returnFocus.getClientRects().length)
      returnFocus.focus({ preventScroll: true });
    else if (returnFocus)
      $(".filter-pill.active").focus({ preventScroll: true });
    returnFocus = null;
  });
  imageWrap.addEventListener(
    "touchstart",
    (event) => {
      touchStart =
        event.touches.length === 1
          ? { x: event.touches[0].clientX, y: event.touches[0].clientY }
          : null;
    },
    { passive: true },
  );
  imageWrap.addEventListener(
    "touchend",
    (event) => {
      if (!touchStart || imageWrap.classList.contains("zoomed")) return;
      const dx = event.changedTouches[0].clientX - touchStart.x;
      const dy = event.changedTouches[0].clientY - touchStart.y;
      if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5)
        navigate(dx < 0 ? 1 : -1);
      touchStart = null;
    },
    { passive: true },
  );
  image.addEventListener("error", () =>
    toast("Не удалось загрузить превью. Попробуйте открыть оригинал."),
  );

  // A minimum-price estimate, with the original pricing and no invented fees.
  const services = {
    "head-basic": {
      name: "Тот самый аватар",
      description: "Рендер головы без дополнительных моделей",
      price: 30,
    },
    "head-models": {
      name: "Чуть больше вас",
      description: "Голова с аксессуарами и моделями",
      price: 50,
    },
    medium: {
      name: "Маленькая история",
      description: "Персонаж в небольшой атмосферной сцене",
      price: 80,
    },
    big: {
      name: "Целый мир",
      description: "Большая сцена с вниманием к деталям",
      price: 120,
    },
  };
  let selectedService = "head-basic";
  const characters = $("#characters");
  function updateOrder() {
    const service = services[selectedService];
    const isScene = selectedService === "medium" || selectedService === "big";
    const count = Math.max(
      0,
      Math.min(20, Math.trunc(Number(characters.value) || 0)),
    );
    characters.value = count;
    $("#characters-minus").disabled = count === 0;
    $("#characters-plus").disabled = count === 20;
    $("#extra-characters").hidden = !isScene;
    $("#order-name").textContent = service.name;
    $("#order-description").textContent = service.description;
    const price = service.price + (isScene ? count * 10 : 0);
    $("#order-price").textContent = `от ${price} ₽`;
    const lines = [
      "Привет, Криспи! Хочу заказать рендер.",
      `Тип: ${service.description}.`,
    ];
    if (isScene) lines.push(`Дополнительных персонажей: ${count}.`);
    const idea = $("#order-idea").value.trim();
    if (idea) lines.push(`Идея: ${idea}`);
    lines.push(`Ориентир: от ${price} ₽. Давай обсудим детали!`);
    $("#order-link").href =
      `https://t.me/Yappy_CriSpy?text=${encodeURIComponent(lines.join("\n"))}`;
  }
  $$(".service-option").forEach((button) =>
    button.addEventListener("click", () => {
      selectedService = button.dataset.service;
      $$(".service-option").forEach((option) => {
        const selected = option === button;
        option.classList.toggle("selected", selected);
        option.setAttribute("aria-pressed", String(selected));
      });
      updateOrder();
    }),
  );
  characters.addEventListener("input", updateOrder);
  $("#characters-minus").addEventListener("click", () => {
    characters.value = Number(characters.value) - 1;
    updateOrder();
  });
  $("#characters-plus").addEventListener("click", () => {
    characters.value = Number(characters.value) + 1;
    updateOrder();
  });
  $("#order-idea").addEventListener("input", updateOrder);
  $("#order-form").addEventListener("submit", (event) =>
    event.preventDefault(),
  );

  $("#copy-contact").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText("@Yappy_CriSpy");
      toast("Скопировано: @Yappy_CriSpy");
    } catch {
      toast("Мой Telegram: @Yappy_CriSpy — можно скопировать вручную.");
    }
  });

  const burger = $("#burger");
  const mobileNav = $("#mobile-nav");
  function setMenu(open) {
    mobileNav.hidden = !open;
    burger.setAttribute("aria-expanded", String(open));
    burger.setAttribute("aria-label", open ? "Закрыть меню" : "Открыть меню");
  }
  burger.addEventListener("click", () => setMenu(mobileNav.hidden));
  $$("#mobile-nav a").forEach((link) =>
    link.addEventListener("click", () => setMenu(false)),
  );
  document.addEventListener("click", (event) => {
    if (!mobileNav.hidden && !event.target.closest(".site-header"))
      setMenu(false);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !mobileNav.hidden) {
      setMenu(false);
      burger.focus();
    }
  });
  matchMedia("(min-width: 761px)").addEventListener("change", (event) => {
    if (event.matches) setMenu(false);
  });

  // One passive listener and at most one layout calculation per animation frame.
  let scrollQueued = false;
  const progress = $(".reading-progress");
  function updateProgress() {
    const distance = document.documentElement.scrollHeight - innerHeight;
    progress.style.transform = `scaleX(${distance > 0 ? Math.min(1, scrollY / distance) : 0})`;
    scrollQueued = false;
  }
  addEventListener(
    "scroll",
    () => {
      if (!scrollQueued) {
        scrollQueued = true;
        requestAnimationFrame(updateProgress);
      }
    },
    { passive: true },
  );
  addEventListener("resize", updateProgress, { passive: true });
  if ("ResizeObserver" in window)
    new ResizeObserver(updateProgress).observe(document.body);
  if ("IntersectionObserver" in window) {
    const navLinks = $$(".desktop-nav a");
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          navLinks.forEach((link) => {
            if (link.hash === `#${entry.target.id}`)
              link.setAttribute("aria-current", "location");
            else link.removeAttribute("aria-current");
          });
        });
      },
      { rootMargin: "-15% 0px -55% 0px" },
    );
    ["renders", "about", "services"].forEach((id) =>
      observer.observe(document.getElementById(id)),
    );
  }

  function restoreURL() {
    const params = new URL(location.href).searchParams;
    state.filter = validFilters.has(params.get("filter"))
      ? params.get("filter")
      : "all";
    state.search = (params.get("q") || "").slice(0, 100).trim();
    state.expanded = false;
    $("#work-search").value = state.search;
    renderGallery({ syncURL: false });
    const work = params.get("work");
    if (byId.has(work)) openLightbox(work);
    else if (dialog.open) dialog.close();
  }
  addEventListener("popstate", restoreURL);
  document.documentElement.classList.add("js");
  syncFavorites();
  restoreURL();
  updateOrder();
  updateProgress();
  $("#year").textContent = new Date().getFullYear();
})();

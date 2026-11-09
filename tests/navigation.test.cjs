const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const appSource = fs.readFileSync(
  path.join(__dirname, "../web/app.js"),
  "utf8"
);

function createEnvironment(lang = "en") {
  class Element {
    constructor() {
      this.attributes = new Map();
      this.listeners = new Map();
      this.children = [];
      this.classNames = new Set();
      this.classList = {
        toggle: (name, force) => {
          if (force) this.classNames.add(name);
          else this.classNames.delete(name);
          return Boolean(force);
        },
        contains: (name) => this.classNames.has(name),
      };
    }

    addEventListener(type, callback) {
      const callbacks = this.listeners.get(type) || [];
      callbacks.push(callback);
      this.listeners.set(type, callbacks);
    }

    emit(type, event = {}) {
      for (const callback of this.listeners.get(type) || []) {
        callback({ target: this, ...event });
      }
    }

    setAttribute(name, value) {
      this.attributes.set(name, value);
    }

    getAttribute(name) {
      return this.attributes.get(name) ?? null;
    }

    contains(target) {
      return target === this || this.children.includes(target);
    }

    querySelectorAll(selector) {
      return selector === "a" ? this.children : [];
    }

    focus() {
      document.activeElement = this;
    }
  }

  const menuButton = new Element();
  const navigation = new Element();
  const link = new Element();
  const outside = new Element();
  navigation.children.push(link);

  const elements = {
    ".menu-toggle": menuButton,
    ".primary-nav": navigation,
  };

  const document = {
    documentElement: { lang },
    activeElement: null,
    listeners: new Map(),
    querySelector: (selector) => elements[selector] || null,
    addEventListener(type, callback) {
      const callbacks = this.listeners.get(type) || [];
      callbacks.push(callback);
      this.listeners.set(type, callbacks);
    },
    emit(type, event = {}) {
      for (const callback of this.listeners.get(type) || []) {
        callback(event);
      }
    },
  };

  const mediaListeners = [];
  const mediaQuery = {
    addEventListener(type, callback) {
      if (type === "change") mediaListeners.push(callback);
    },
    emit(matches) {
      for (const callback of mediaListeners) callback({ matches });
    },
  };

  const window = {
    matchMedia: (query) => {
      assert.equal(query, "(min-width: 721px)");
      return mediaQuery;
    },
  };

  vm.runInNewContext(appSource, { document, window, Boolean, String });

  return { menuButton, navigation, link, outside, document, mediaQuery };
}

test("menu button opens and closes with synchronized accessibility state", () => {
  const { menuButton, navigation } = createEnvironment();

  assert.equal(navigation.classList.contains("open"), false);
  assert.equal(menuButton.getAttribute("aria-expanded"), "false");
  assert.equal(menuButton.getAttribute("aria-label"), "Open navigation");

  menuButton.emit("click");
  assert.equal(navigation.classList.contains("open"), true);
  assert.equal(menuButton.getAttribute("aria-expanded"), "true");
  assert.equal(menuButton.getAttribute("aria-label"), "Close navigation");

  menuButton.emit("click");
  assert.equal(navigation.classList.contains("open"), false);
  assert.equal(menuButton.getAttribute("aria-expanded"), "false");
  assert.equal(menuButton.getAttribute("aria-label"), "Open navigation");
});

test("selecting a navigation link closes the menu", () => {
  const { menuButton, navigation, link } = createEnvironment();
  menuButton.emit("click");
  link.emit("click");
  assert.equal(navigation.classList.contains("open"), false);
  assert.equal(menuButton.getAttribute("aria-expanded"), "false");
});

test("Escape closes the menu and restores focus to the menu button", () => {
  const { menuButton, navigation, document } = createEnvironment();
  menuButton.emit("click");
  document.emit("keydown", { key: "Escape" });
  assert.equal(navigation.classList.contains("open"), false);
  assert.equal(menuButton.getAttribute("aria-expanded"), "false");
  assert.equal(document.activeElement, menuButton);
});

test("clicking outside closes the menu without stealing focus", () => {
  const { menuButton, navigation, outside, document } = createEnvironment();
  menuButton.emit("click");
  document.activeElement = outside;
  document.emit("click", { target: outside });
  assert.equal(navigation.classList.contains("open"), false);
  assert.equal(menuButton.getAttribute("aria-expanded"), "false");
  assert.equal(document.activeElement, outside);
});

test("entering desktop breakpoint resets the mobile menu state", () => {
  const { menuButton, navigation, mediaQuery } = createEnvironment();
  menuButton.emit("click");
  mediaQuery.emit(true);
  assert.equal(navigation.classList.contains("open"), false);
  assert.equal(menuButton.getAttribute("aria-expanded"), "false");
  assert.equal(menuButton.getAttribute("aria-label"), "Open navigation");
});

test("Arabic page uses Arabic menu labels", () => {
  const { menuButton } = createEnvironment("ar");
  assert.equal(menuButton.getAttribute("aria-label"), "فتح القائمة");
  menuButton.emit("click");
  assert.equal(menuButton.getAttribute("aria-label"), "إغلاق القائمة");
});

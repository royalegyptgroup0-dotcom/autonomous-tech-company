const menuButton = document.querySelector(".menu-toggle");
const navigation = document.querySelector(".primary-nav");

if (menuButton && navigation) {
  const isArabic = document.documentElement.lang === "ar";
  const desktopMediaQuery = window.matchMedia("(min-width: 721px)");
  let isMenuOpen = false;

  function setMenuState(isOpen, { returnFocus = false } = {}) {
    isMenuOpen = Boolean(isOpen);
    navigation.classList.toggle("open", isMenuOpen);
    menuButton.setAttribute("aria-expanded", String(isMenuOpen));
    menuButton.setAttribute(
      "aria-label",
      isArabic
        ? (isMenuOpen ? "إغلاق القائمة" : "فتح القائمة")
        : (isMenuOpen ? "Close navigation" : "Open navigation")
    );

    if (!isMenuOpen && returnFocus) {
      menuButton.focus();
    }
  }

  menuButton.addEventListener("click", () => {
    setMenuState(!isMenuOpen);
  });

  navigation.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      setMenuState(false);
    });
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && isMenuOpen) {
      setMenuState(false, { returnFocus: true });
    }
  });

  document.addEventListener("click", (event) => {
    if (
      isMenuOpen &&
      !navigation.contains(event.target) &&
      !menuButton.contains(event.target)
    ) {
      setMenuState(false);
    }
  });

  desktopMediaQuery.addEventListener("change", (event) => {
    if (event.matches) {
      setMenuState(false);
    }
  });

  setMenuState(false);
}

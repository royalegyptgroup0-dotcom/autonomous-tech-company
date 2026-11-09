const menuButton = document.querySelector(".menu-toggle");
const navigation = document.querySelector(".primary-nav");

if (menuButton && navigation) {
  menuButton.addEventListener("click", () => {
    const isOpen = navigation.classList.toggle("open");
    menuButton.setAttribute("aria-expanded", String(isOpen));
    menuButton.setAttribute("aria-label", document.documentElement.lang === "ar" ? (isOpen ? "إغلاق القائمة" : "فتح القائمة") : (isOpen ? "Close navigation" : "Open navigation"));
  });

  navigation.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      navigation.classList.remove("open");
      menuButton.setAttribute("aria-expanded", "false");
      menuButton.setAttribute("aria-label", document.documentElement.lang === "ar" ? "فتح القائمة" : "Open navigation");
    });
  });
}


document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && navigation?.classList.contains("open")) {
    navigation.classList.remove("open");
    menuButton?.setAttribute("aria-expanded", "false");
    menuButton?.setAttribute("aria-label", document.documentElement.lang === "ar" ? "فتح القائمة" : "Open navigation");
    menuButton?.focus();
  }
});

(function () {
  "use strict";
  let stored = null;
  try {
    stored = localStorage.getItem("localagent-site-theme");
  } catch (_error) {
    stored = null;
  }
  const theme = stored === "light" || stored === "dark" ? stored : "auto";
  const resolved = theme === "auto"
    ? (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
    : theme;
  document.documentElement.dataset.theme = resolved;
  document.documentElement.dataset.themePreference = theme;
})();

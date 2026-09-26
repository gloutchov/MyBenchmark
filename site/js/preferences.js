(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.LocalAgentSitePreferences = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const LANGUAGE_KEY = "localagent-site-language";
  const THEME_KEY = "localagent-site-theme";
  const THEMES = new Set(["auto", "light", "dark"]);

  function languagePreference(stored, browserLanguage) {
    if (stored === "it" || stored === "en") return stored;
    return typeof browserLanguage === "string" && browserLanguage.toLowerCase().startsWith("it") ? "it" : "en";
  }

  function themePreference(stored) {
    return THEMES.has(stored) ? stored : "auto";
  }

  function resolveTheme(preference, prefersDark) {
    return preference === "auto" ? (prefersDark ? "dark" : "light") : themePreference(preference);
  }

  return { LANGUAGE_KEY, THEME_KEY, languagePreference, themePreference, resolveTheme };
});

"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const ROOT = path.resolve(__dirname, "..", "..");
const SITE = path.join(ROOT, "site");
const i18n = require(path.join(SITE, "js", "i18n.js"));
const preferences = require(path.join(SITE, "js", "preferences.js"));

function htmlKeys(file) {
  const html = fs.readFileSync(path.join(SITE, file), "utf8");
  const keys = new Set();
  for (const match of html.matchAll(/data-i18n(?:-aria-label|-alt|-content)?="([a-z0-9_]+)"/g)) keys.add(match[1]);
  return keys;
}

test("Italian and English dictionaries stay synchronized", () => {
  assert.deepEqual(Object.keys(i18n.STRINGS.it).sort(), Object.keys(i18n.STRINGS.en).sort());
});

test("every declared translation key exists in both languages", () => {
  const keys = new Set([...htmlKeys("index.html"), ...htmlKeys("404.html")]);
  for (const key of keys) {
    assert.equal(typeof i18n.STRINGS.it[key], "string", `missing Italian key: ${key}`);
    assert.equal(typeof i18n.STRINGS.en[key], "string", `missing English key: ${key}`);
  }
});

test("language detection uses Italian only for Italian locales", () => {
  assert.equal(i18n.normalizeLanguage("it-IT"), "it");
  assert.equal(i18n.normalizeLanguage("it"), "it");
  assert.equal(i18n.normalizeLanguage("en-US"), "en");
  assert.equal(i18n.normalizeLanguage("fr-FR"), "en");
  assert.equal(preferences.languagePreference(null, "it-CH"), "it");
  assert.equal(preferences.languagePreference(null, "de-DE"), "en");
  assert.equal(preferences.languagePreference("en", "it-IT"), "en");
});

test("theme preference validates values and resolves automatic mode", () => {
  assert.equal(preferences.themePreference("light"), "light");
  assert.equal(preferences.themePreference("dark"), "dark");
  assert.equal(preferences.themePreference("broken"), "auto");
  assert.equal(preferences.resolveTheme("auto", true), "dark");
  assert.equal(preferences.resolveTheme("auto", false), "light");
  assert.equal(preferences.resolveTheme("light", true), "light");
});

test("the site has no remote runtime assets or inline executable scripts", () => {
  for (const file of ["index.html", "404.html"]) {
    const html = fs.readFileSync(path.join(SITE, file), "utf8");
    assert.doesNotMatch(html, /<(?:script|img)[^>]+src="https?:/i);
    assert.doesNotMatch(html, /<link(?=[^>]+rel="(?:stylesheet|icon)")[^>]+href="https?:/i);
    assert.doesNotMatch(html, /<script(?![^>]+src=)[^>]*>\s*\S/i);
    assert.match(html, /connect-src 'none'/);
  }
  const css = fs.readFileSync(path.join(SITE, "css", "styles.css"), "utf8");
  assert.doesNotMatch(css, /@import|url\(\s*["']?https?:/i);
});

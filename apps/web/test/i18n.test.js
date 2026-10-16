import test from "node:test";
import assert from "node:assert/strict";

import { DEFAULT_LOCALE, LOCALES, isLocale, keys, translate } from "../src/lib/i18n.js";

test("translate returns the requested locale's string", () => {
  assert.equal(translate("en", "nav.inbox"), "Inbox");
  assert.equal(translate("km", "nav.inbox"), "ទូរចូល");
  assert.equal(translate("km", "nav.settings"), "ការកំណត់");
});

test("translate falls back to English for a locale missing a key", () => {
  assert.equal(translate("km", "shell.language"), "ភាសា");
  // A key present in English but not Khmer still resolves.
  assert.equal(translate("km", "nav.inbox"), "ទូរចូល");
  assert.equal(translate("fr", "nav.inbox"), "Inbox");
});

test("translate falls back to the caller's fallback, then the key", () => {
  assert.equal(translate("en", "nope.missing", "Fallback"), "Fallback");
  assert.equal(translate("en", "nope.missing"), "nope.missing");
  assert.equal(translate(undefined, "nope.missing", "Fallback"), "Fallback");
});

test("every locale covers exactly the English keys", () => {
  const english = keys();
  assert.ok(english.length > 10);
  for (const { id } of LOCALES) {
    for (const key of english) {
      assert.notEqual(translate(id, key), key, `${id} is missing ${key}`);
    }
  }
});

test("isLocale guards unknown values", () => {
  assert.equal(isLocale("en"), true);
  assert.equal(isLocale("km"), true);
  assert.equal(isLocale("fr"), false);
  assert.equal(isLocale(null), false);
  assert.equal(DEFAULT_LOCALE, "en");
});

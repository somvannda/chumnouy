// Tiny console i18n layer: a flat key → string map per locale, no dependencies.
//
// Scope is deliberately the shell (navigation and a few shared labels); page
// bodies stay in English until they are translated. Workspace *content* locale
// (notifications, help centre) is a separate setting — see
// /v1/console/settings/locale.

export const LOCALES = [
  { id: "en", label: "EN" },
  { id: "km", label: "ខ្មែរ" },
];

export const DEFAULT_LOCALE = "en";

const STRINGS = {
  en: {
    "nav.inbox": "Inbox",
    "nav.chat": "Live chat",
    "nav.reports": "Reports",
    "nav.assistant": "Assistant",
    "nav.knowledge": "Knowledge",
    "nav.requesters": "Requesters",
    "nav.members": "Members",
    "nav.teams": "Teams",
    "nav.webhooks": "Webhooks",
    "nav.triggers": "Triggers",
    "nav.automations": "Automations",
    "nav.canned": "Canned",
    "nav.macros": "Macros",
    "nav.audit": "Audit",
    "nav.integrations": "Integrations",
    "nav.settings": "Settings",
    "nav.admin": "Admin",
    "shell.workspace": "Workspace",
    "shell.toggleTheme": "Toggle theme",
    "shell.signOut": "Sign out",
    "shell.language": "Language",
  },
  km: {
    "nav.inbox": "ទូរចូល",
    "nav.chat": "ជជែកផ្ទាល់",
    "nav.reports": "របាយការណ៍",
    "nav.assistant": "ជំនួយការ",
    "nav.knowledge": "ចំណេះដឹង",
    "nav.requesters": "អ្នកស្នើសុំ",
    "nav.members": "សមាជិក",
    "nav.teams": "ក្រុម",
    "nav.webhooks": "Webhook",
    "nav.triggers": "កេះ",
    "nav.automations": "ស្វ័យប្រវត្តិ",
    "nav.canned": "ចម្លើយស្រាប់",
    "nav.macros": "ម៉ាក្រូ",
    "nav.audit": "សវនកម្ម",
    "nav.integrations": "ការភ្ជាប់",
    "nav.settings": "ការកំណត់",
    "nav.admin": "អ្នកគ្រប់គ្រង",
    "shell.workspace": "កន្លែងធ្វើការ",
    "shell.toggleTheme": "ប្តូររចនាប័ទ្ម",
    "shell.signOut": "ចាកចេញ",
    "shell.language": "ភាសា",
  },
};

export function isLocale(value) {
  return Object.prototype.hasOwnProperty.call(STRINGS, value);
}

export function keys() {
  return Object.keys(STRINGS[DEFAULT_LOCALE]);
}

export function translate(locale, key, fallback) {
  const table = STRINGS[isLocale(locale) ? locale : DEFAULT_LOCALE];
  const value = table?.[key];
  if (value) return value;
  // Fall back to English, then to the key's own fallback, then the key.
  const english = STRINGS[DEFAULT_LOCALE][key];
  return english || fallback || key;
}

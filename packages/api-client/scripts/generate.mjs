#!/usr/bin/env node
// Generates src/schema.ts from the committed OpenAPI spec.
//
// Dependency-free on purpose: it reads chumnouy_api/openapi.json and emits a
// TypeScript interface/type for every component schema. Run from anywhere:
//
//     node packages/api-client/scripts/generate.mjs
//
// The committed src/schema.ts is the artifact; regenerate it whenever the API
// contract changes (CI regenerates openapi.json and fails on drift).

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const SPEC_PATH = resolve(HERE, "../../../chumnouy_api/openapi.json");
const OUT_PATH = resolve(HERE, "../src/schema.ts");

const spec = JSON.parse(readFileSync(SPEC_PATH, "utf8"));
const schemas = spec.components?.schemas ?? {};

const isNullSchema = (s) => s && (s.type === "null" || (Array.isArray(s.enum) && s.enum.length === 1 && s.enum[0] === null));

function refName(ref) {
  return ref.split("/").pop();
}

function typeOf(schema) {
  if (!schema) return "unknown";
  if (schema.$ref) return refName(schema.$ref);
  if (Array.isArray(schema.enum)) {
    return schema.enum.map((v) => JSON.stringify(v)).join(" | ") || "unknown";
  }
  if (schema.const !== undefined) return JSON.stringify(schema.const);

  const variants = schema.anyOf || schema.oneOf;
  if (Array.isArray(variants)) {
    const parts = [...new Set(variants.map(typeOf))];
    return parts.join(" | ");
  }
  if (Array.isArray(schema.allOf)) {
    const parts = [...new Set(schema.allOf.map(typeOf))];
    return parts.join(" & ");
  }

  switch (schema.type) {
    case "string":
      return "string";
    case "integer":
    case "number":
      return "number";
    case "boolean":
      return "boolean";
    case "null":
      return "null";
    case "array":
      return `${typeOf(schema.items)}[]`;
    case "object": {
      if (schema.additionalProperties === true) return "Record<string, unknown>";
      if (schema.additionalProperties && typeof schema.additionalProperties === "object") {
        return `Record<string, ${typeOf(schema.additionalProperties)}>`;
      }
      if (schema.properties) {
        return `{ ${Object.entries(schema.properties)
          .map(([k, v]) => `${k}${(schema.required || []).includes(k) ? "" : "?"}: ${typeOf(v)}`)
          .join("; ")} }`;
      }
      return "Record<string, unknown>";
    }
    default:
      return "unknown";
  }
}

function docComment(schema, indent) {
  const text = schema.title || schema.description;
  if (!text) return "";
  return `${indent}/** ${String(text).replace(/\*\//g, "*\\/").replace(/\n/g, " ")} */\n`;
}

const lines = [
  "/* eslint-disable */",
  "// AUTO-GENERATED from chumnouy_api/openapi.json - do not edit by hand.",
  "// Regenerate with: node packages/api-client/scripts/generate.mjs",
  "",
];

for (const [name, schema] of Object.entries(schemas)) {
  if (schema.type === "object" && schema.properties) {
    lines.push(`${docComment(schema, "")}export interface ${name} {`);
    const required = schema.required || [];
    for (const [prop, propSchema] of Object.entries(schema.properties)) {
      const doc = docComment(propSchema, "  ").trimEnd();
      if (doc) lines.push(doc);
      lines.push(`  ${prop}${required.includes(prop) ? "" : "?"}: ${typeOf(propSchema)};`);
    }
    lines.push("}", "");
  } else {
    lines.push(`export type ${name} = ${typeOf(schema)};`, "");
  }
}

// Drop any blank comment artifacts.
const output = lines.filter((l) => l !== undefined).join("\n").replace(/\n{3,}/g, "\n\n");
mkdirSync(dirname(OUT_PATH), { recursive: true });
writeFileSync(OUT_PATH, `${output.trimEnd()}\n`, "utf8");
console.log(`wrote ${OUT_PATH} (${Object.keys(schemas).length} schemas)`);

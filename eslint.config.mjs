import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // Python virtualenv — some deps (e.g. litellm, pulled in by guardrails-ai) bundle their own
    // pre-built JS admin UIs inside the installed package, which ESLint would otherwise happily
    // try to lint as if it were our own source.
    ".venv/**",
  ]),
]);

export default eslintConfig;

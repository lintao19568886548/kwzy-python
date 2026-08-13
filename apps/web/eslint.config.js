import vue from "eslint-plugin-vue";
import tsParser from "@typescript-eslint/parser";
import vueParser from "vue-eslint-parser";

export default [
  {
    ignores: ["dist/**", "node_modules/**", "playwright-report/**"],
  },
  {
    files: ["src/**/*.{ts,vue}"],
    languageOptions: {
      parser: vueParser,
      parserOptions: {
        parser: tsParser,
        ecmaVersion: "latest",
        sourceType: "module",
      },
    },
    plugins: { vue },
    rules: {
      "vue/multi-word-component-names": "off",
      "no-unused-vars": "off",
    },
  },
];

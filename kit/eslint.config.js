import js from "@eslint/js";
import prettier from "eslint-config-prettier";
import svelte from "eslint-plugin-svelte";
import globals from "globals";
import ts from "typescript-eslint";

export default ts.config(
	{
		ignores: ["**/*.cjs", "build/", ".svelte-kit/", "package/", "static/"],
	},
	js.configs.recommended,
	...ts.configs.recommended,
	...svelte.configs.recommended,
	prettier,
	...svelte.configs.prettier,
	{
		languageOptions: {
			globals: {
				...globals.browser,
				...globals.node,
				// Injected at build time via Vite `define` (see vite.config.ts)
				__DOCS_LIBRARY__: "readonly",
				__DOCS_VERSION__: "readonly",
				__DOCS_LANGUAGE__: "readonly",
			},
		},
	},
	{
		files: ["**/*.svelte"],
		languageOptions: {
			parserOptions: {
				parser: ts.parser,
			},
		},
	},
	{
		rules: {
			"no-shadow": ["error"],
			"@typescript-eslint/no-explicit-any": "error",
			"@typescript-eslint/no-non-null-assertion": "error",
			"@typescript-eslint/no-unused-vars": [
				// prevent variables with a _ prefix from being marked as unused
				"error",
				{
					argsIgnorePattern: "^_",
					varsIgnorePattern: "^_",
				},
			],
			// The whole point of doc-builder is rendering generated (trusted) HTML
			"svelte/no-at-html-tags": "off",
			// Doc links are plain prerendered hrefs by design
			"svelte/no-navigation-without-resolve": "off",
			// Pre-existing unkeyed each blocks; keying them changes update semantics
			"svelte/require-each-key": "off",
		},
	}
);

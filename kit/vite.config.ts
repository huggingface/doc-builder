import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";

export default defineConfig({
	plugins: [sveltekit()],
	define: {
		// Compile-time constants used by getHfDocFullPath ($lib/hfDocPaths.js).
		// String(undefined) === "undefined" never matches a real library/version/lang,
		// which disables shorthand-path expansion in dev (same as the old replace.js).
		__DOCS_LIBRARY__: JSON.stringify(String(process.env.DOCS_LIBRARY)),
		__DOCS_VERSION__: JSON.stringify(String(process.env.DOCS_VERSION)),
		__DOCS_LANGUAGE__: JSON.stringify(String(process.env.DOCS_LANGUAGE)),
	},
	build: {
		sourcemap: Boolean(process.env.DOCS_SOURCEMAP),
	},
});

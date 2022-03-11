import adapter from "@sveltejs/adapter-static";
import preprocess from "svelte-preprocess";
import { docstringPreprocess, frameworkcontentPreprocess, mdsvexPreprocess } from "./preprocess.js";

/** @type {import('@sveltejs/kit').Config} */
const config = {
	extensions: [".svelte", ".mdx"],

	// Consult https://github.com/sveltejs/svelte-preprocess
	// for more information about preprocessors
	preprocess: [
		docstringPreprocess,
		frameworkcontentPreprocess,
		mdsvexPreprocess,
		preprocess({ sourceMap: Boolean(process.env.DOCS_SOURCEMAP) })
	],

	kit: {
		adapter: adapter(),
		// inlineStyleThreshold: 100_000,
		browser: {
			hydrate: true,
			router: false
		},

		prerender: {
			crawl: false // Do not throw if linked page doesn't exist (eg when forgetting the language prefix)
		},

		vite: {
			build: {
				sourcemap: Boolean(process.env.DOCS_SOURCEMAP)
			}
		},

		paths: {
			base:
				"/docs/" +
				(process.env.DOCS_LIBRARY || "transformers") +
				"/" +
				(process.env.DOCS_VERSION || "master") +
				"/" +
				(process.env.DOCS_LANGUAGE || "en")
		}
	},

	onwarn: (warning, handler) => {
		if (
			warning.message.includes("has unused export property 'fw'") ||
			warning.message.includes("A11y")
		) {
			/// Too noisy
			return;
		}
		handler(warning);
	}
};

export default config;

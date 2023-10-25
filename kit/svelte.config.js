import adapter from "@sveltejs/adapter-static";
import { vitePreprocess } from "@sveltejs/kit/vite";

import {
	docstringPreprocess,
	frameworkcontentPreprocess,
	mdsvexPreprocess,
	inferenceSnippetPreprocess,
	tokenizersLangPreprocess,
	hfOptionsPreprocess,
} from "./preprocessors/index.js";

/** @type {import('@sveltejs/kit').Config} */
const config = {
	// Consult https://kit.svelte.dev/docs/integrations#preprocessors
	// for more information about preprocessors
	preprocess: [
		docstringPreprocess,
		frameworkcontentPreprocess,
		inferenceSnippetPreprocess,
		tokenizersLangPreprocess,
		hfOptionsPreprocess,
		mdsvexPreprocess,
		vitePreprocess({}),
	],

	kit: {
		// adapter-auto only supports some environments, see https://kit.svelte.dev/docs/adapter-auto for a list.
		// If your environment is not supported or you settled on a specific environment, switch out the adapter.
		// See https://kit.svelte.dev/docs/adapters for more information about adapters.
		adapter: adapter({ strict: false }),

		prerender: {
			crawl: false, // Do not throw if linked page doesn't exist (eg when forgetting the language prefix)
		},

		paths: {
			base: process.argv.includes("dev")
				? ""
				: "/docs/" +
				  (process.env.DOCS_LIBRARY || "transformers") +
				  "/" +
				  (process.env.DOCS_VERSION || "main") +
				  "/" +
				  (process.env.DOCS_LANGUAGE || "en"),
			relative: false,
		},
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
	},
};

export default config;

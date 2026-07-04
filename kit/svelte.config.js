import adapter from "@sveltejs/adapter-static";
import { vitePreprocess } from "@sveltejs/vite-plugin-svelte";

import {
	docstringPreprocess,
	frameworkcontentPreprocess,
	mdsvexPreprocess,
	inferenceSnippetPreprocess,
	tokenizersLangPreprocess,
	hfOptionsPreprocess,
	hashInCodePreprocess,
} from "./preprocessors/index.js";

/** @type {import('@sveltejs/kit').Config} */
const config = {
	// Consult https://svelte.dev/docs/kit/integrations
	// for more information about preprocessors
	preprocess: [
		hashInCodePreprocess,
		docstringPreprocess,
		frameworkcontentPreprocess,
		inferenceSnippetPreprocess,
		tokenizersLangPreprocess,
		hfOptionsPreprocess,
		mdsvexPreprocess,
		vitePreprocess({}),
	],

	kit: {
		// adapter-auto only supports some environments, see https://svelte.dev/docs/kit/adapter-auto for a list.
		// If your environment is not supported or you settled on a specific environment, switch out the adapter.
		// See https://svelte.dev/docs/kit/adapters for more information about adapters.
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
			warning.message.includes("unused export property") ||
			warning.code?.startsWith("a11y") ||
			warning.message.includes("A11y") ||
			// md-generated doc content is full of `<video ... />` style self-closing tags
			warning.code === "element_invalid_self_closing_tag" ||
			// initial-value capture of props is intentional here: doc pages pass
			// static props (same semantics as the pre-runes svelte 4 code)
			warning.code === "state_referenced_locally"
		) {
			/// Too noisy
			return;
		}
		handler(warning);
	},
};

export default config;

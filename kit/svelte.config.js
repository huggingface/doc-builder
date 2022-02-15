import adapter from '@sveltejs/adapter-static';
import preprocess from 'svelte-preprocess';
import { docstringPreprocess, mdsvexPreprocess } from './preprocess.js';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	extensions: ['.svelte', '.mdx'],

	// Consult https://github.com/sveltejs/svelte-preprocess
	// for more information about preprocessors
	preprocess: [docstringPreprocess, mdsvexPreprocess, preprocess()],

	kit: {
		adapter: adapter(),
		browser: {
			hydrate: false,
			router: false
		},

		prerender: {
			crawl: false // Do not throw if linked page doesn't exist (eg when forgetting the language prefix)
		}
	},
};

export default config;

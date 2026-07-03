// See https://kit.svelte.dev/docs/types#app
// for information about these interfaces
declare global {
	// Injected at build time via Vite `define` (see vite.config.ts)
	const __DOCS_LIBRARY__: string;
	const __DOCS_VERSION__: string;
	const __DOCS_LANGUAGE__: string;

	namespace App {
		// interface Error {}
		// interface Locals {}
		// interface PageData {}
		// interface Platform {}
	}
}

export {};

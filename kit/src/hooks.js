import { getHfDocFullPath } from "$lib/hfDocPaths.js";

/**
 * Map shorthand hf doc URLs (e.g. /docs/lib/page) to the full route
 * (/docs/lib/version/lang/page) so they are resolved as internal routes.
 * Replaces the old `svelteKitCustomClient` fork of `@sveltejs/kit`'s client.js.
 * @type {import('@sveltejs/kit').Reroute}
 */
export function reroute({ url }) {
	return getHfDocFullPath(url.pathname);
}

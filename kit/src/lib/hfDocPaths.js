/**
 * In hf docs, these redirection rules exist:
 *   hf.co/docs/lib/page         -> hf.co/docs/lib/default_version/default_lang/page
 *   hf.co/docs/lib/version/page -> hf.co/docs/lib/version/default_lang/page
 * This helper expands such shorthand doc paths to the full path of the
 * currently built library/version/language, so that they can be treated as
 * internal SvelteKit routes (partial loading) instead of full page reloads.
 *
 * `__DOCS_LIBRARY__` & co are compile-time constants injected via Vite `define`
 * (see vite.config.ts) from the DOCS_LIBRARY/DOCS_VERSION/DOCS_LANGUAGE env vars.
 *
 * @param {string} pathname
 * @returns {string|undefined} the full pathname, or undefined if `pathname` does
 * not belong to the currently built library/version/language
 */
export function getHfDocFullPath(pathname) {
	if (/^\/(docs|learn)/.test(pathname)) {
		const params = pathname.slice(1).split("/");
		const _docType = params.shift();
		const _library = params.shift();
		const isCourse = _docType === "learn";
		const versionRegex = isCourse ? /^(?:pr_\d+)$/ : /^(?:(master|main)|v[\d.]+(rc\d+)?|pr_\d+)$/;
		const _version = versionRegex.test(params[0]) ? params.shift() : __DOCS_VERSION__;
		const _lang = /^[a-z]{2}(-[A-Z]{2})?$/.test(params[0]) ? params.shift() : __DOCS_LANGUAGE__;
		const newChapterId = params.join("/");
		if (
			__DOCS_LIBRARY__ === _library &&
			__DOCS_VERSION__ === _version &&
			__DOCS_LANGUAGE__ === _lang
		) {
			return `/docs/${__DOCS_LIBRARY__}/${__DOCS_VERSION__}/${__DOCS_LANGUAGE__}/${newChapterId}`;
		}
	}
	return;
}

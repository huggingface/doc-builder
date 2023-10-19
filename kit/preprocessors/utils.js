/**
 * Async string replace function.
 * src: https://github.com/dsblv/string-replace-async
 * @param {string} string
 * @param {RegExp} searchValue
 * @param {Function | string} replacer
 */
export async function replaceAsync(string, searchValue, replacer) {
	if (typeof replacer === "function") {
		// 1. Run fake pass of `replace`, collect values from `replacer` calls
		// 2. Resolve them with `Promise.all`
		// 3. Run `replace` with resolved values
		const values = [];
		String.prototype.replace.call(string, searchValue, function () {
			values.push(replacer.apply(undefined, arguments));
			return "";
		});
		const resolvedValues = await Promise.all(values);
		return String.prototype.replace.call(string, searchValue, function () {
			return resolvedValues.shift();
		});
	}
	return String.prototype.replace.call(string, searchValue, replacer);
}

/**
 * Render escaped characters like `<`, `{`.
 * used for Doc
 * @param {string} code
 */
export function renderSvelteChars(code) {
	return code.replace(/&amp;lcub;/g, "{").replace(/&amp;lt;/g, "<");
}

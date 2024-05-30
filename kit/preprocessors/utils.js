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
 * Render escaped characters like `<`, `{`, '#'.
 * used for Doc
 * @param {string} code
 */
export function renderSvelteChars(code) {
	return code
		.replace(/&amp;lcub;/g, "{")
		.replace(/&amp;lt;/g, "<")
		.replace(/&amp;num;/g, "#");
}

/**
 * Create a regex that captures html-like opening and closing tag and its contents.
 * used for parsing hf custom syntax
 * example: generateTagRegex("inferenceSnippet", true) -> /<inferenceSnippet>(.*?)<\/inferenceSnippet>/msg
 * @param {string} tag - The name of the tag to match content within.
 * @param {boolean} [global=false] - Whether to create a global pattern that matches all occurrences.
 * @returns {RegExp} - The generated RegExp pattern.
 */
export function generateTagRegex(tag, global = false) {
	const flags = global ? "msg" : "ms";
	const pattern = new RegExp(`<${tag}>(.*?)<\\/${tag}>`, flags);
	return pattern;
}

/**
 * Create a regex that captures html-like opening and closing tag with attribute "id" and its contents.
 * used for parsing hf custom syntax
 * example: generateTagRegex("inferenceSnippet", true) -> /<inferenceSnippet\s+id=["'](.+)["']\s*>(.*?)<\/inferenceSnippet>/msg
 * @param {string} tag - The name of the tag to match content within.
 * @param {boolean} [global=false] - Whether to create a global pattern that matches all occurrences.
 * @returns {RegExp} - The generated RegExp pattern.
 */
export function generateTagRegexWithId(tag, global = false) {
	const flags = global ? "msg" : "ms";
	const pattern = new RegExp(`<${tag}\\s+id=["'](.+?)["']\\s*>(.*?)<\\/${tag}>`, flags);
	return pattern;
}

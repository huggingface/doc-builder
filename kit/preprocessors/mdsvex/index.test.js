// Run from kit/ (index.js lists ./src/lib at import time): npm test
import { test } from "node:test";
import assert from "node:assert/strict";
import { DOCSTRING_FRAGMENT_MARKER, mdsvexPreprocess } from "./index.js";

/** @param {string} markdown */
async function render(markdown) {
	const content = `HF_DOC_BODY_START\n\n${markdown}\n\nHF_DOC_BODY_END\n`;
	const { code } = await mdsvexPreprocess.markup({ content, filename: "docs/+page.svelte" });
	return code;
}

/**
 * Renders markdown as a docstring fragment, like docstring.js does
 * @param {string} markdown
 */
async function renderFragment(markdown) {
	const content = `${DOCSTRING_FRAGMENT_MARKER}\n\n${markdown}`;
	const { code } = await mdsvexPreprocess.markup({ content, filename: "docs/+page.svelte" });
	return code;
}

/** @param {string} code */
function codeBlockSources(code) {
	return [...code.matchAll(/<CodeBlock\s+code=\{`([^`]*)`\}/g)].map(([, base64]) =>
		decodeURIComponent(atob(base64))
	);
}

test("callout with plain text", async () => {
	const html = await render("> [!NOTE]\n> Some text.");
	assert.match(html, /<blockquote class="note">\s*<p>Some text\.<\/p>/);
});

test("callout whose content starts with a link", async () => {
	const html = await render(
		"> [!NOTE]\n> [Managed accounts](./enterprise-advanced-sso), which sign in through their identity provider."
	);
	assert.match(
		html,
		/<blockquote class="note">\s*<p><a href="\.\/enterprise-advanced-sso">Managed accounts<\/a>, which/
	);
});

test("callout marker followed by a hard line break", async () => {
	const html = await render("> [!NOTE]  \n> [the docs](./a) explain it.");
	assert.match(
		html,
		/<blockquote class="note">\s*<p><a href="\.\/a">the docs<\/a> explain it\.<\/p>/
	);
});

test("callout marker and link on the same line", async () => {
	const html = await render("> [!TIP] [the docs](./a) explain it.");
	assert.match(
		html,
		/<blockquote class="tip">\s*<p><a href="\.\/a">the docs<\/a> explain it\.<\/p>/
	);
});

test("callout continued lazily with a link", async () => {
	const html = await render("> [!WARNING]\n[the docs](./a) explain it.");
	assert.match(
		html,
		/<blockquote class="warning">\s*<p><a href="\.\/a">the docs<\/a> explain it\.<\/p>/
	);
});

test("nested callout whose content starts with a link", async () => {
	const html = await render("> > [!CAUTION]\n> > [the docs](./a) explain it.");
	assert.match(
		html,
		/<blockquote class="caution">\s*<p><a href="\.\/a">the docs<\/a> explain it\.<\/p>/
	);
});

test("link after bracketed text in prose", async () => {
	const html = await render("Arguments [optional] [link](./a) and [optional]\n[link](./b).");
	assert.match(html, /\[optional\] <a href="\.\/a">link<\/a>/);
	assert.match(html, /\[optional\]\n<a href="\.\/b">link<\/a>/);
});

test("full and collapsed reference links still resolve", async () => {
	const html = await render("See [the docs][docs] and [docs][].\n\n[docs]: ./a");
	assert.match(html, /See <a href="\.\/a">the docs<\/a> and <a href="\.\/a">docs<\/a>\./);
});

test("callout examples in code blocks stay as written", async () => {
	const nested = "```md\n> ```py\n> x = 1\n> ```\n```";
	const example = "```\n> [!NOTE]\n> [link](./a) text\n```";
	const html = await render(`${nested}\n\nSome prose.\n\n${example}`);
	assert.deepEqual(codeBlockSources(html), [
		"> ```py\n> x = 1\n> ```",
		"> [!NOTE]\n> [link](./a) text",
	]);
});

test("math in the page body is a Svelte {@html} tag", async () => {
	const html = await render("Mixing gate $g$ and \\\\(z_t\\\\) of $\\frac{1}{2}$ here.");
	const tags = [...html.matchAll(/\{@html ("(?:[^"\\]|\\.)*")\}/g)].map(([, json]) =>
		JSON.parse(json)
	);
	assert.equal(tags.length, 3);
	assert.ok(tags.every((tag) => tag.startsWith('<span class="katex">')));
});

test("math in a docstring fragment is KaTeX HTML", async () => {
	// the `}}` of docstring fragments are escaped by docstring.js
	const html = await renderFragment(
		"Mixing gate $g$ and \\\\(z_t\\\\) of $\\frac{1}{\\sqrt{2}&zwnj;}$ here."
	);
	assert.doesNotMatch(html, /@html/);
	assert.equal(html.match(/<span class="katex">/g)?.length, 3);
	assert.match(
		html,
		/<annotation encoding="application\/x-tex">\\frac\{1\}\{\\sqrt\{2\}\}<\/annotation>/
	);
});

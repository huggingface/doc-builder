// Run from kit/ (index.js lists ./src/lib at import time): npm test
import { test } from "node:test";
import assert from "node:assert/strict";
import { mdsvexPreprocess } from "./index.js";

/** @param {string} markdown */
async function render(markdown) {
	const content = `HF_DOC_BODY_START\n\n${markdown}\n\nHF_DOC_BODY_END\n`;
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

import assert from "node:assert/strict";
import test from "node:test";
import { mdsvexPreprocess } from "./index.js";

async function renderCodeBlock(lang, code) {
	const result = await mdsvexPreprocess.markup({
		content: `\n\`\`\`${lang}\n${code}\n\`\`\`\n`,
		filename: "/docs/+page.svelte",
	});
	return result.code;
}

const csv = `file_name,text
images/1.jpg,a drawing of a green pokemon with red eyes
images/2.jpg,a green and yellow toy with a red nose
images/3.jpg,a red and white ball with an angry look on its face
images/4.jpg,a cartoon ball with a smile on it's face`;

test("CSV fences do not receive unrelated syntax highlighting", async () => {
	const result = await renderCodeBlock("csv", csv);
	assert.doesNotMatch(result, /hljs-/);
	assert.match(result, /lang="csv"/);
	assert.ok(result.includes(btoa(encodeURIComponent(csv))));
});

test("unsupported languages render escaped plain text", async () => {
	const result = await renderCodeBlock("unsupported-language", '<tag attr="value"> & text');
	assert.doesNotMatch(result, /hljs-/);
	assert.match(result, /&lt;tag attr=&quot;value&quot;&gt; &amp; text/);
});

test("supported languages keep syntax highlighting", async () => {
	const result = await renderCodeBlock("python", 'print("hello")');
	assert.match(result, /hljs-built_in/);
	assert.match(result, /lang="python"/);
});

test("fences without a language keep automatic highlighting", async () => {
	const result = await renderCodeBlock("", csv);
	assert.match(result, /hljs-/);
});

test("CSV framework blocks use plain text for both groups", async () => {
	const result = await renderCodeBlock("csv", `${csv}\n===PT-TF-SPLIT===\n${csv}`);
	assert.match(result, /<CodeBlockFw/);
	assert.doesNotMatch(result, /hljs-/);
});

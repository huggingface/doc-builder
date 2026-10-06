import assert from "node:assert/strict";
import test from "node:test";
import { markKatex } from "./index.js";

// MDX pages pass `\\(...\\)` (two backslashes) into markKatex, matching
// `convert_rst_to_mdx` / notebook conversion.

test("inline \\(...\\) keeps the space before the formula", () => {
	const marked = {};
	const result = markKatex("one step \\\\(S_{t+1}\\\\) later", marked);
	assert.equal(result, "one step KATEXPARSE0MARKER later");
	assert.equal(marked.KATEXPARSE0MARKER.tex, "S_{t+1}");
	assert.equal(marked.KATEXPARSE0MARKER.displayMode, false);
});

test("consecutive \\(...\\) lines keep the separating newline", () => {
	const marked = {};
	const result = markKatex("text \\\\(a\\\\)\n\\\\(b\\\\)", marked);
	assert.equal(result, "text KATEXPARSE0MARKER\nKATEXPARSE1MARKER");
	assert.equal(marked.KATEXPARSE0MARKER.tex, "a");
	assert.equal(marked.KATEXPARSE1MARKER.tex, "b");
});

test("display $$...$$ keeps the leading newline", () => {
	const marked = {};
	const result = markKatex("before\n$$x + y$$\nafter", marked);
	assert.equal(result, "before\nKATEXPARSE0MARKER\nafter");
	assert.equal(marked.KATEXPARSE0MARKER.tex, "x + y");
	assert.equal(marked.KATEXPARSE0MARKER.displayMode, true);
});

test("inline $...$ still restores surrounding whitespace", () => {
	const marked = {};
	const result = markKatex("see $x$ here", marked);
	assert.equal(result, "see KATEXPARSE0MARKER here");
	assert.equal(marked.KATEXPARSE0MARKER.tex, "x");
});

// Golden test of docstring rendering, kit half: renders the snapshotted MDX of the Python half
// (tests/test_docstring_snapshots.py, which explains how to regenerate both) and compares the HTML
// of the docstrings with the snapshot. Run from kit/: npm test
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile, writeFile } from "fs/promises";
import { fileURLToPath } from "url";
import { createDocstringRenderer } from "./docstring-snapshots.js";

const snapshotDir = new URL("../../tests/data/docstring_snapshots/", import.meta.url);

test("docstrings render to the snapshotted HTML", async () => {
	const renderer = await createDocstringRenderer();
	let html;
	try {
		html = await renderer.render(fileURLToPath(new URL("page.mdx", snapshotDir)));
	} finally {
		await renderer.close();
	}
	const snapshot = new URL("page.html", snapshotDir);
	if (process.env.UPDATE_SNAPSHOTS) {
		await writeFile(snapshot, html);
	}
	assert.equal(html, await readFile(snapshot, "utf8"));
});

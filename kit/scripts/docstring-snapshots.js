// Renders doc pages, as written by `doc-builder build`, to the final HTML of their docstrings: through
// the docs build's Vite/SvelteKit config (preprocessors, mdsvex) and Svelte SSR. Used by the docstring
// snapshot test (docstring-snapshots.test.js), and to diff the docstrings of a whole library before and
// after a change of the docstring pipeline:
//
//   doc-builder build transformers ~/transformers/docs/source/en --build_dir /tmp/before
//   cd kit && node scripts/docstring-snapshots.js /tmp/before /tmp/before-html
//   (same with the change, then) diff -r /tmp/before-html /tmp/after-html
//
// Run from kit/ (the mdsvex preprocessor lists ./src/lib when imported).
import { mkdtemp, mkdir, copyFile, rm, readdir, readFile, writeFile } from "fs/promises";
import { tmpdir } from "os";
import path from "path";
import { fileURLToPath } from "url";
import * as cheerio from "cheerio";
import prettier from "prettier";
import { createServer } from "vite";

const kitDir = fileURLToPath(new URL("..", import.meta.url));

export async function createDocstringRenderer() {
	const pagesDir = await mkdtemp(path.join(tmpdir(), "docstring-snapshots-"));
	const server = await createServer({
		configFile: path.join(kitDir, "vite.config.ts"),
		appType: "custom",
		logLevel: "error",
		server: { middlewareMode: true, hmr: false, watch: null },
	});
	// the svelte runtime the pages are compiled against
	const { render } = await server.ssrLoadModule("svelte/server");
	let pageCount = 0;

	return {
		/**
		 * @param {string} file a page (`.mdx` or `+page.svelte`) written by `doc-builder build`
		 * @returns {Promise<string>} the formatted HTML of the page's docstrings
		 */
		async render(file) {
			// the mdsvex preprocessor only handles SvelteKit page files
			const page = path.join(pagesDir, String(pageCount++), "+page.svelte");
			await mkdir(path.dirname(page));
			await copyFile(file, page);
			const { default: Page } = await server.ssrLoadModule(page);
			return formatDocstrings(render(Page).body);
		},
		async close() {
			await server.close();
			await rm(pagesDir, { recursive: true, force: true });
		},
	};
}

/**
 * Extracts the docstrings (the outermost `.docstring` blocks, with their methods) from a rendered
 * page. Svelte's hydration comments and icons are dropped to keep the snapshots readable.
 * @param {string} html
 */
async function formatDocstrings(html) {
	const $ = cheerio.load(html, null, false);
	const docstrings = $(".docstring").filter((_, el) => $(el).parents(".docstring").length === 0);
	docstrings.find("svg").replaceWith("<svg></svg>");
	docstrings
		.find("*")
		.contents()
		.filter((_, node) => node.type === "comment")
		.remove();
	const formatted = [];
	for (const el of docstrings.toArray()) {
		formatted.push(await prettier.format($.html(el), { parser: "html", printWidth: 100 }));
	}
	return formatted.join("\n");
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
	const [inDir, outDir] = process.argv.slice(2);
	if (!inDir || !outDir) {
		console.error("usage: node scripts/docstring-snapshots.js <build dir> <output dir>");
		process.exit(1);
	}
	const renderer = await createDocstringRenderer();
	try {
		const files = (await readdir(inDir, { recursive: true }))
			.filter((file) => file.endsWith(".mdx") || path.basename(file) === "+page.svelte")
			.sort();
		for (const file of files) {
			const content = await readFile(path.join(inDir, file), "utf8");
			if (!content.includes("<Docstring")) {
				continue;
			}
			const out = path.join(outDir, file.replace(/(\/\+page\.svelte|\.mdx)$/, ".html"));
			try {
				const html = await renderer.render(path.join(inDir, file));
				await mkdir(path.dirname(out), { recursive: true });
				await writeFile(out, html);
				console.log(out);
			} catch (error) {
				console.error(`${file}: ${error instanceof Error ? error.message : error}`);
			}
		}
	} finally {
		await renderer.close();
	}
}

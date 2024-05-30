import hljs from "highlight.js";
import { mdsvex } from "mdsvex";
import katex from "katex";
import { visit } from "unist-util-visit";
import htmlTags from "html-tags";
import { readdir } from "fs/promises";
import path from "path";
import cheerio from "cheerio";
import { renderSvelteChars } from "../utils.js";

/**
 * inside `<code>` html elements, we need to replace `&amp;` with `&`
 * to correctly render escaped characters like `<`, `{`, etc.
 * used for Doc
 * @param {string} code
 */
function renderCode(code) {
	const REGEX_CODE_TAG = /<code>(((?!<code>).)*)<\/code>/gms;
	return code.replace(
		REGEX_CODE_TAG,
		(_, group1) => `<code>${group1.replace(/&amp;/gm, "&")}</code>`
	);
}

const WRAP_CODE_BLOCKS_FLAG = "<!-- WRAP CODE BLOCKS -->";
let wrapCodeBlocks = false;

export const mdsvexPreprocess = {
	markup: async ({ content, filename }) => {
		if (filename.endsWith("+page.svelte")) {
			const markedKatex = {};
			// if (filename.includes("course/")) {
			// 	content = addCourseImports(content);
			// }
			wrapCodeBlocks = content.includes(WRAP_CODE_BLOCKS_FLAG);
			content = markKatex(content, markedKatex);
			content = escapeSvelteConditionals(content);
			const processed = await _mdsvexPreprocess.markup({ content, filename });
			processed.code = renderKatex(processed.code, markedKatex);
			processed.code = renderCode(processed.code, filename);
			return processed;
		}
		return { code: content };
	},
};

/**
 * Latex support in mdsvex
 * @param {string} content
 * @param {Record<any, any>} markedKatex
 */
function markKatex(content, markedKatex) {
	const REGEX_LATEX_DISPLAY = /\n\$\$([\s\S]+?)\$\$/g;
	const REGEX_LATEX_INLINE = /\s\\\\\(([\s\S]+?)\\\\\)/g;
	let counter = 0;
	return content
		.replace(REGEX_LATEX_DISPLAY, (_, tex) => {
			const displayMode = true;
			const marker = `KATEXPARSE${counter++}MARKER`;
			markedKatex[marker] = { tex, displayMode };
			return marker;
		})
		.replace(REGEX_LATEX_INLINE, (_, tex) => {
			const displayMode = false;
			const marker = `KATEXPARSE${counter++}MARKER`;
			markedKatex[marker] = { tex, displayMode };
			return marker;
		});
}

function renderKatex(code, markedKatex) {
	return code.replace(/KATEXPARSE[0-9]+MARKER/g, (marker) => {
		let { tex, displayMode } = markedKatex[marker];
		tex = tex.replaceAll("&#123;", "{");
		tex = tex.replaceAll("&#60;", "<");
		const html = katex.renderToString(renderSvelteChars(tex), {
			displayMode,
			throwOnError: false,
		});
		if (html.includes(`katex-error`)) {
			throw new Error(`[KaTeX] Error while parsing markdown\n ${html}`);
		}
		return `{@html ${JSON.stringify(html)}}`;
	});
}

async function findSvelteComponentNames(startDir) {
	let svelteFiles = [];

	async function searchDir(directory) {
		const files = await readdir(directory, { withFileTypes: true });

		for (const file of files) {
			const filePath = path.join(directory, file.name);
			if (file.isDirectory()) {
				await searchDir(filePath);
			} else if (path.extname(file.name) === ".svelte") {
				svelteFiles.push(path.basename(file.name, ".svelte")); // strip the directory and .svelte extension
			}
		}
	}

	await searchDir(startDir);
	return svelteFiles;
}

const dirPath = "./src/lib";
const svelteTags = await findSvelteComponentNames(dirPath);
const validTags = [...htmlTags, ...svelteTags];
let hfDocBodyStart = false;
let hfDocBodyEnd = false;

function addToTree(tree, node) {
	if (tree.length === 0 || tree[tree.length - 1].depth >= node.depth) {
		tree.push(node);
	} else {
		const sections = tree[tree.length - 1].sections || [];
		tree[tree.length - 1].sections = addToTree(sections, node);
	}
	return tree;
}

function getTitleText(node) {
	if (!node.children || node.children.length === 0) {
		return node.value ? node.value.trim() : "";
	}

	return node.children
		.map((child) => getTitleText(child))
		.join(" ")
		.trim();
}

function treeVisitor() {
	return transform;

	function transform(tree) {
		let headings = [];
		visit(tree, "heading", (node, index, parent) => {
			const depth = node.depth;
			let title = getTitleText(node);
			let local = "";
			const match = title.match(/\[\s(.*?)\s\]$/);
			if (match && match[1]) {
				local = match[1];
				title = title.replace(match[0], "").trim();
			} else {
				local = title
					.trim()
					.toLowerCase()
					.replace(/\s+/g, "-") // Replace spaces with hyphens
					.replace(/[^\p{L}\p{N}-]+/gu, ""); // Keep letters, numbers, and hyphens only
			}
			headings = addToTree(headings, { title, local, sections: [], depth });

			// Create a svelte node (in remark grammar, the type is "html")
			const svelteNode = {
				type: "html",
				value: `<Heading title="${title.replaceAll(
					"{",
					"&#123;"
				)}" local="${local}" headingTag="h${depth}"/>`,
			};
			// Replace the old node with the new Svelte node
			parent.children[index] = svelteNode;
		});
		visit(tree, "text", onText);
		visit(tree, "html", onHtml);
		visit(tree, "blockquote", onBlockquote);

		let jsonString = JSON.stringify(headings[0]);
		if (jsonString) {
			jsonString = jsonString.replaceAll("'", "\\'");
		}

		tree.children.unshift({
			type: "html",
			value: `<script context="module">export const metadata = '${jsonString}';</script>`,
		});
	}

	function isWithinDocBody(node) {
		if (["<!--HF DOCBUILD BODY START-->", "HF_DOC_BODY_START"].includes(node.value)) {
			hfDocBodyStart = true;
			hfDocBodyEnd = false;
			// delete the marker
			if (node.value === "HF_DOC_BODY_START") {
				node.value = "";
			}
		}
		if (["<!--HF DOCBUILD BODY END-->", "HF_DOC_BODY_END"].includes(node.value)) {
			hfDocBodyEnd = true;
			// delete the marker
			if (node.value === "HF_DOC_BODY_END") {
				node.value = "";
			}
		}
		return hfDocBodyStart && !hfDocBodyEnd;
	}

	function onText(node) {
		if (!isWithinDocBody(node)) {
			return;
		}
		node.value = node.value.replaceAll("{", "&#123;");
		node.value = node.value.replaceAll("<", "&#60;");
	}

	function onHtml(node) {
		if (!isWithinDocBody(node)) {
			return;
		}
		const RE_TAG_NAME = /<\/?(\w+)/;
		const match = node.value.match(RE_TAG_NAME);
		const REGEX_VALID_START_END_TAG = /^<(\w+)[^>]*>.*<\/\1>$/s;
		if (match) {
			const tagName = match[1];
			if (!validTags.includes(tagName)) {
				node.value = node.value.replaceAll("<", "&#60;");
			} else if (htmlTags.includes(tagName) && REGEX_VALID_START_END_TAG.test(node.value.trim())) {
				const $ = cheerio.load(node.value);
				// Go through each text node in the HTML and replace "{" with "&#123;"
				$("*")
					.contents()
					.each((index, element) => {
						if (element.type === "text") {
							element.data = element.data.replaceAll("{", "&#123;");
						}
					});
				// Update the remark HTML node with the modified HTML
				node.value = $("body").html();
			}
		}
	}

	function onBlockquote(node, index, parent) {
		// use github-like Tip & Warning syntax
		// see https://github.com/orgs/community/discussions/16925
		const { children: childrenLevel1 } = node;
		if (!childrenLevel1.length || childrenLevel1[0].type !== "paragraph") {
			return;
		}

		const { children: childrenLevel2 } = childrenLevel1[0];
		if (!childrenLevel2.length || childrenLevel2[0].type !== "linkReference") {
			return;
		}

		const TIP_MARKERS = ["!tip", "!warning"];
		const { identifier } = childrenLevel2[0];
		if (!TIP_MARKERS.includes(identifier)) {
			return;
		}

		if (!parent) {
			return;
		}

		childrenLevel1[0].children = childrenLevel1[0].children.slice(1);
		const nodeTagOpen = {
			type: "html",
			value: `<Tip warning={${identifier === "!warning"}}>\n\n`,
		};
		const nodeTagClose = {
			type: "html",
			value: "\n\n</Tip>",
		};
		const nodes = [nodeTagOpen, ...childrenLevel1, nodeTagClose];
		parent.children.splice(index, 1, ...nodes);
	}
}

const _mdsvexPreprocess = mdsvex({
	remarkPlugins: [treeVisitor],
	extensions: ["svelte"],
	highlight: {
		highlighter: function (code, lang) {
			const REGEX_CODE_INPUT = /^(>>>\s|\.\.\.\s)/m;
			const _highlight = (code) =>
				lang && hljs.getLanguage(lang)
					? hljs.highlight(lang, code, true).value
					: hljs.highlightAuto(code).value;
			const base64 = (val) => btoa(encodeURIComponent(val));
			const escape = (code) =>
				code.replace(/\\/g, "\\\\").replace(/`/g, "\\`").replace(/}/g, "\\}").replace(/\$/g, "\\$");
			const REGEX_FRAMEWORKS_SPLIT = /\s*===(PT-TF|STRINGAPI-READINSTRUCTION)-SPLIT===\s*/gm;

			code = renderSvelteChars(code);
			if (code.match(REGEX_FRAMEWORKS_SPLIT)) {
				const isPtTf = code.match(REGEX_FRAMEWORKS_SPLIT)[0].includes("PT-TF");
				let [codeGroup1, _, codeGroup2] = code.split(REGEX_FRAMEWORKS_SPLIT);
				const highlightedPt = _highlight(codeGroup1);
				const highlightedTf = _highlight(codeGroup2);
				// filter out outputs if the code was generated interactively
				// `>>> for i in range(5):` becomes `for i in range(5):`
				if (codeGroup1.match(REGEX_CODE_INPUT)) {
					codeGroup1 = codeGroup1
						.split("\n")
						.filter((line) => line.match(REGEX_CODE_INPUT) || !line)
						.map((line) => line.replace(REGEX_CODE_INPUT, ""))
						.join("\n");
				}
				if (codeGroup2.match(REGEX_CODE_INPUT)) {
					codeGroup2 = codeGroup2
						.split("\n")
						.filter((line) => line.match(REGEX_CODE_INPUT) || !line)
						.map((line) => line.replace(REGEX_CODE_INPUT, ""))
						.join("\n");
				}
				return `
	<CodeBlockFw
		group1={{
			id: '${isPtTf ? "pt" : "stringapi"}',
			code: \`${base64(codeGroup1)}\`,
			highlighted: \`${escape(highlightedPt)}\`
		}}
		group2={{
			id: '${isPtTf ? "tf" : "readinstruction"}',
			code: \`${base64(codeGroup2)}\`,
			highlighted: \`${escape(highlightedTf)}\`
		}}
		wrap={${wrapCodeBlocks}}
	/>`;
			} else {
				const highlighted = _highlight(code);
				// filter out outputs if the code was generated interactively
				// `>>> for i in range(5):` becomes `for i in range(5):`
				if (code.match(REGEX_CODE_INPUT)) {
					code = code
						.split("\n")
						.filter((line) => line.match(REGEX_CODE_INPUT) || !line)
						.map((line) => line.replace(REGEX_CODE_INPUT, ""))
						.join("\n");
				}
				return `
	<CodeBlock 
		code={\`${base64(code)}\`}
		highlighted={\`${escape(highlighted)}\`}
		wrap={${wrapCodeBlocks}}
	/>`;
			}
		},
	},
});

function escapeSvelteConditionals(code) {
	const REGEX_SVELTE_IF_START = /(\{#if[^}]+\})/g;
	const SVELTE_ELSE = "{:else}";
	const SVELTE_IF_END = "{/if}";
	code = code.replace(REGEX_SVELTE_IF_START, "\n\n$1\n\n");
	code = code.replaceAll(SVELTE_ELSE, `\n\n${SVELTE_ELSE}\n\n`);
	code = code.replaceAll(SVELTE_IF_END, `\n\n${SVELTE_IF_END}\n\n`);
	return code;
}

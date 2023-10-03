import domUtils from "domutils";
import htmlparser2 from "htmlparser2";
import hljs from "highlight.js";
import { mdsvex } from "mdsvex";
import katex from "katex";
import { visit } from "unist-util-visit";
import htmlTags from "html-tags";
import { readdir } from "fs/promises";
import path from "path";
import cheerio from "cheerio";

// Preprocessor that converts markdown into Docstring
// svelte component using mdsvexPreprocess
export const docstringPreprocess = {
	markup: async ({ content, filename }) => {
		const REGEX_DOCSTRING = /<docstring>(((?!<docstring>).)*)<\/docstring>/gms;
		const REGEX_NAME = /<name>(((?!<name>).)*)<\/name>/ms;
		const REGEX_ANCHOR = /<anchor>(((?!<anchor>).)*)<\/anchor>/ms;
		const REGEX_SIGNATURE = /<parameters>(((?!<parameters>).)*)<\/parameters>/ms;
		const REGEX_PARAMSDESC = /<paramsdesc>(((?!<paramsdesc>).)*)<\/paramsdesc>/ms;
		const REGEX_PARAMSGROUPS = /<paramgroups>(((?!<paramgroups>).)*)<\/paramgroups>/ms;
		const REGEX_RETDESC = /<retdesc>(((?!<retdesc>).)*)<\/retdesc>/ms;
		const REGEX_RETTYPE = /<rettype>(((?!<rettype>).)*)<\/rettype>/ms;
		const REGEX_YIELDESC = /<yieldesc>(((?!<yieldesc>).)*)<\/yieldesc>/ms;
		const REGEX_YIELDTYPE = /<yieldtype>(((?!<yieldtype>).)*)<\/yieldtype>/ms;
		const REGEX_RAISEDESC = /<raises>(((?!<raises>).)*)<\/raises>/ms;
		const REGEX_RAISETYPE = /<raisederrors>(((?!<raisederrors>).)*)<\/raisederrors>/ms;
		const REGEX_SOURCE = /<source>(((?!<source>).)*)<\/source>/ms;
		const REGEX_TIP = /<Tip( warning={true})?>(((?!<Tip( warning={true})?>).)*)<\/Tip>/gms;
		const REGEX_CHANGED =
			/<(Added|Changed|Deprecated) version="([0-9.v]+)" ?\/?>((((?!<(Added|Changed|Deprecated) version="([0-9.v]+)"\/?>).)*)<\/(Added|Changed|Deprecated)>)?/gms;
		const REGEX_IS_GETSET_DESC = /<isgetsetdescriptor>/ms;

		content = await replaceAsync(content, REGEX_DOCSTRING, async (_, docstringBody) => {
			docstringBody = renderSvelteChars(docstringBody);

			const name = docstringBody.match(REGEX_NAME)[1];
			const anchor = docstringBody.match(REGEX_ANCHOR)[1];
			const signature = docstringBody.match(REGEX_SIGNATURE)[1];

			let svelteComponent = `<Docstring name={${JSON.stringify(
				unescapeUnderscores(name)
			)}} anchor={${JSON.stringify(anchor)}} parameters={${signature}} `;

			if (docstringBody.match(REGEX_PARAMSDESC)) {
				let content = docstringBody.match(REGEX_PARAMSDESC)[1];
				// escape }} by adding void character `&zwnj;` in between
				content = content.replace(/}}/g, "}&zwnj;}");
				let { code } = await mdsvexPreprocess.markup({ content, filename });
				// render <Tip> components that are inside parameter descriptions
				code = code.replace(REGEX_TIP, (_, isWarning, tipContent) => {
					const color = isWarning ? "orange" : "green";
					return `<div
						class="course-tip ${
							color === "orange" ? "course-tip-orange" : ""
						} bg-gradient-to-br dark:bg-gradient-to-r before:border-${color}-500 dark:before:border-${color}-800 from-${color}-50 dark:from-gray-900 to-white dark:to-gray-950 border border-${color}-50 text-${color}-700 dark:text-gray-400"
					>
						${tipContent}
					</div>`;
				});
				// render <Added>, <Changed>, <Deprecated> components that are inside parameter descriptions
				code = code.replace(REGEX_CHANGED, (_, componentType, version, __, descriptionContent) => {
					const color = /Added|Changed/.test(componentType) ? "green" : "orange";
					if (!descriptionContent) {
						descriptionContent = "";
					}
					return `<div
						class="course-tip ${
							color === "orange" ? "course-tip-orange" : ""
						} bg-gradient-to-br dark:bg-gradient-to-r before:border-${color}-500 dark:before:border-${color}-800 from-${color}-50 dark:from-gray-900 to-white dark:to-gray-950 border border-${color}-50 text-${color}-700 dark:text-gray-400"
					>
						<p class="font-medium">${componentType} in ${version}</p>
						${descriptionContent}
					</div>`;
				});

				const dom = htmlparser2.parseDocument(code);
				const lists = domUtils.getElementsByTagName("ul", dom);
				if (lists.length) {
					const list = lists[0];
					const result = [];
					for (const childEl of list.childNodes.filter(({ type }) => type === "tag")) {
						const nameEl = domUtils.getElementsByTagName("strong", childEl)[0];
						const name = domUtils.innerText(nameEl);
						const paramAnchor = `${anchor}.${name}`;
						let description = domUtils.getInnerHTML(childEl).trim();

						// strip enclosing paragraph tags <p> & </p>
						if (description.startsWith("<p>")) {
							description = description.slice("<p>".length);
						}
						if (description.endsWith("</p>")) {
							description = description.slice(0, -"</p>".length);
						}

						result.push({ anchor: paramAnchor, description, name });
					}
					svelteComponent += ` parametersDescription={${JSON.stringify(result)}} `;
				}
			}

			if (docstringBody.match(REGEX_SOURCE)) {
				const source = docstringBody.match(REGEX_SOURCE)[1];
				svelteComponent += ` source={${JSON.stringify(source)}} `;
			}

			if (docstringBody.match(REGEX_RETDESC)) {
				const retDesc = docstringBody.match(REGEX_RETDESC)[1];
				const { code } = await mdsvexPreprocess.markup({ content: retDesc, filename });
				svelteComponent += ` returnDescription={${JSON.stringify(code)}} `;
			}

			if (docstringBody.match(REGEX_RETTYPE)) {
				const retType = docstringBody.match(REGEX_RETTYPE)[1];
				const { code } = await mdsvexPreprocess.markup({ content: retType, filename });
				svelteComponent += ` returnType={${JSON.stringify(code)}} `;
			}

			if (docstringBody.match(REGEX_YIELDESC)) {
				const yieldDesc = docstringBody.match(REGEX_YIELDESC)[1];
				const { code } = await mdsvexPreprocess.markup({ content: yieldDesc, filename });
				svelteComponent += ` returnDescription={${JSON.stringify(code)}} `;
			}

			if (docstringBody.match(REGEX_YIELDTYPE)) {
				const yieldType = docstringBody.match(REGEX_YIELDTYPE)[1];
				const { code } = await mdsvexPreprocess.markup({ content: yieldType, filename });
				svelteComponent += ` returnType={${JSON.stringify(code)}} isYield={true} `;
			}

			if (docstringBody.match(REGEX_RAISEDESC)) {
				const raiseDesc = docstringBody.match(REGEX_RAISEDESC)[1];
				const { code } = await mdsvexPreprocess.markup({ content: raiseDesc, filename });
				svelteComponent += ` raiseDescription={${JSON.stringify(code)}} `;
			}

			if (docstringBody.match(REGEX_RAISETYPE)) {
				const raiseType = docstringBody.match(REGEX_RAISETYPE)[1];
				const { code } = await mdsvexPreprocess.markup({ content: raiseType, filename });
				svelteComponent += ` raiseType={${JSON.stringify(code)}} `;
			}

			if (docstringBody.match(REGEX_IS_GETSET_DESC)) {
				svelteComponent += ` isGetSetDescriptor={true} `;
			}

			if (docstringBody.match(REGEX_PARAMSGROUPS)) {
				const nParamGroups = parseInt(docstringBody.match(REGEX_PARAMSGROUPS)[1]);
				if (nParamGroups > 0) {
					const parameterGroups = [];
					for (let groupId = 1; groupId <= nParamGroups; groupId++) {
						const REGEX_GROUP_TITLE = new RegExp(
							`<paramsdesc${groupId}title>(((?!<paramsdesc${groupId}title>).)*)</paramsdesc${groupId}title>`,
							"ms"
						);
						const REGEX_GROUP_CONTENT = new RegExp(
							`<paramsdesc${groupId}>(((?!<paramsdesc${groupId}>).)*)</paramsdesc${groupId}>`,
							"ms"
						);
						const title = docstringBody.match(REGEX_GROUP_TITLE)[1];
						const content = docstringBody.match(REGEX_GROUP_CONTENT)[1];
						const { code } = await mdsvexPreprocess.markup({ content, filename });
						const dom = htmlparser2.parseDocument(code);
						const lists = domUtils.getElementsByTagName("ul", dom);
						const result = [];
						if (lists.length) {
							const list = lists[0];
							for (const childEl of list.childNodes.filter(({ type }) => type === "tag")) {
								const nameEl = domUtils.getElementsByTagName("strong", childEl)[0];
								const name = domUtils.innerText(nameEl);
								const paramAnchor = `${anchor}.${name}`;
								let description = domUtils.getInnerHTML(childEl).trim();

								// strip enclosing paragraph tags <p> & </p>
								if (description.startsWith("<p>")) {
									description = description.slice("<p>".length);
								}
								if (description.endsWith("</p>")) {
									description = description.slice(0, -"</p>".length);
								}

								result.push({ anchor: paramAnchor, description, name });
							}
						}
						parameterGroups.push({ title, parametersDescription: result });
					}
					svelteComponent += ` parameterGroups={${JSON.stringify(parameterGroups)}} `;
				}
			}

			svelteComponent += ` />\n`;
			return svelteComponent;
		});

		return { code: content };
	},
};

// Preprocessor that converts markdown into FrameworkContent
// svelte component using mdsvexPreprocess
export const frameworkcontentPreprocess = {
	markup: async ({ content }) => {
		const REGEX_FRAMEWORKCONTENT =
			/<frameworkcontent>(((?!<frameworkcontent>).)*)<\/frameworkcontent>/gms;
		const REGEX_PYTORCH = /<pt>(((?!<pt>).)*)<\/pt>/ms;
		const REGEX_TENSORFLOW = /<tf>(((?!<tf>).)*)<\/tf>/ms;
		const REGEX_JAX = /<jax>(((?!<jax>).)*)<\/jax>/ms;

		content = await replaceAsync(content, REGEX_FRAMEWORKCONTENT, async (_, fwcontentBody) => {
			const FRAMEWORKS = [
				{ framework: "pytorch", REGEX_FW: REGEX_PYTORCH, isExist: false },
				{ framework: "tensorflow", REGEX_FW: REGEX_TENSORFLOW, isExist: false },
				{ framework: "jax", REGEX_FW: REGEX_JAX, isExist: false },
			];

			let svelteSlots = "";

			for (const [i, value] of Object.entries(FRAMEWORKS)) {
				const { framework, REGEX_FW } = value;
				if (fwcontentBody.match(REGEX_FW)) {
					FRAMEWORKS[i].isExist = true;
					const fwContent = fwcontentBody.match(REGEX_FW)[1];
					svelteSlots += `<svelte:fragment slot="${framework}">
					<Markdown>
					\n\n${fwContent}\n\n
					</Markdown>
					</svelte:fragment>`;
				}
			}

			const svelteProps = FRAMEWORKS.map((fw) => `${fw.framework}={${fw.isExist}}`).join(" ");

			return `\n\n<FrameworkContent ${svelteProps}>\n${svelteSlots}\n</FrameworkContent>\n\n`;
		});

		return { code: content };
	},
};

// Preprocessor that converts markdown into InferenceApi
// svelte component using mdsvexPreprocess
export const inferenceSnippetPreprocess = {
	markup: async ({ content }) => {
		const REGEX_FRAMEWORKCONTENT =
			/<inferencesnippet>(((?!<inferencesnippet>).)*)<\/inferencesnippet>/gms;
		const REGEX_PYTHON = /<python>(((?!<python>).)*)<\/python>/ms;
		const REGEX_JS = /<js>(((?!<js>).)*)<\/js>/ms;
		const REGEX_CURL = /<curl>(((?!<curl>).)*)<\/curl>/ms;
		const FRAMEWORKS = [
			{ framework: "python", REGEX_FW: REGEX_PYTHON, isExist: false },
			{ framework: "js", REGEX_FW: REGEX_JS, isExist: false },
			{ framework: "curl", REGEX_FW: REGEX_CURL, isExist: false },
		];

		content = await replaceAsync(content, REGEX_FRAMEWORKCONTENT, async (_, fwcontentBody) => {
			let svelteSlots = "";

			for (const [i, value] of Object.entries(FRAMEWORKS)) {
				const { framework, REGEX_FW } = value;
				if (fwcontentBody.match(REGEX_FW)) {
					FRAMEWORKS[i].isExist = true;
					const fwContent = fwcontentBody.match(REGEX_FW)[1];
					svelteSlots += `<svelte:fragment slot="${framework}">
					<Markdown>
					\n\n${fwContent}\n\n
					</Markdown>
					</svelte:fragment>`;
				}
			}

			const svelteProps = FRAMEWORKS.map((fw) => `${fw.framework}={${fw.isExist}}`).join(" ");

			return `<InferenceApi ${svelteProps}>\n${svelteSlots}\n</InferenceApi>`;
		});

		return { code: content };
	},
};

// Preprocessor that converts markdown into TokenizersLanguageContent
// svelte component using mdsvexPreprocess
export const tokenizersLangPreprocess = {
	markup: async ({ content }) => {
		const REGEX_FRAMEWORKCONTENT =
			/<tokenizerslangcontent>(((?!<tokenizerslangcontent>).)*)<\/tokenizerslangcontent>/gms;
		const REGEX_PYTHON = /<python>(((?!<python>).)*)<\/python>/ms;
		const RGEX_RUST = /<rust>(((?!<rust>).)*)<\/rust>/ms;
		const REGEX_NODE = /<node>(((?!<node>).)*)<\/node>/ms;
		const FRAMEWORKS = [
			{ framework: "python", REGEX_FW: REGEX_PYTHON, isExist: false },
			{ framework: "rust", REGEX_FW: RGEX_RUST, isExist: false },
			{ framework: "node", REGEX_FW: REGEX_NODE, isExist: false },
		];

		content = await replaceAsync(content, REGEX_FRAMEWORKCONTENT, async (_, fwcontentBody) => {
			let svelteSlots = "";

			for (const [i, value] of Object.entries(FRAMEWORKS)) {
				const { framework, REGEX_FW } = value;
				if (fwcontentBody.match(REGEX_FW)) {
					FRAMEWORKS[i].isExist = true;
					const fwContent = fwcontentBody.match(REGEX_FW)[1];
					svelteSlots += `<svelte:fragment slot="${framework}">
					<Markdown>
					\n\n${fwContent}\n\n
					</Markdown>
					</svelte:fragment>`;
				}
			}

			const svelteProps = FRAMEWORKS.map((fw) => `${fw.framework}={${fw.isExist}}`).join(" ");

			return `<TokenizersLanguageContent ${svelteProps}>\n${svelteSlots}\n</TokenizersLanguageContent>`;
		});

		return { code: content };
	},
};

/**
 * Async string replace function.
 * src: https://github.com/dsblv/string-replace-async
 * @param {string} string
 * @param {RegExp} searchValue
 * @param {Function | string} replacer
 */
async function replaceAsync(string, searchValue, replacer) {
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
 * Render escaped characters like `<`, `{`.
 * used for Doc
 * @param {string} code
 */
function renderSvelteChars(code) {
	return code.replace(/&amp;lcub;/g, "{").replace(/&amp;lt;/g, "<");
}

/**
 * The mdx file contains unnecessarily escaped underscores in the docstring's name
 */
function unescapeUnderscores(content) {
	return content.replace(/\\_/g, "_");
}

/**
 * Latex support in mdsvex
 * @param {string} content
 * @param {Record<any, any>} markedKatex
 */
function markKatex(content, markedKatex) {
	const REGEX_LATEX_DISPLAY = /\$\$([\s\S]+?)\$\$/g;
	const REGEX_LATEX_INLINE = /\\\\\(([\s\S]+?)\\\\\)/g;
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
		let html = katex.renderToString(renderSvelteChars(tex), {
			displayMode,
			throwOnError: false,
		});
		html = html.replace("katex-html", "katex-html hidden");
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

function escapeSvelteSpecialChars() {
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
					.replace(/[^\w\s-]/g, "")
					.replace(/[\s_-]+/g, "-");
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

		tree.children.unshift({
			type: "html",
			value: `<script context="module">export const metadata = '${JSON.stringify(headings)}';</script>`,
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
}

const _mdsvexPreprocess = mdsvex({
	remarkPlugins: [escapeSvelteSpecialChars],
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

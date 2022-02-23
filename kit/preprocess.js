import domUtils from "domutils";
import htmlparser2 from "htmlparser2";
import hljs from "highlight.js";
import { mdsvex } from "mdsvex";
import katex from "katex";

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
		const REGEX_SOURCE = /<source>(((?!<source>).)*)<\/source>/ms;
		const REGEX_TIP = /<Tip( warning={true})?>(((?!<Tip( warning={true})?>).)*)<\/Tip>/gms;

		content = await replaceAsync(content, REGEX_DOCSTRING, async (_, docstringBody) => {
			docstringBody = renderSvelteChars(docstringBody);

			const name = docstringBody.match(REGEX_NAME)[1];
			const anchor = docstringBody.match(REGEX_ANCHOR)[1];
			const signature = docstringBody.match(REGEX_SIGNATURE)[1];
			const source = docstringBody.match(REGEX_SOURCE)[1];

			let svelteComponent = `<Docstring name={${JSON.stringify(
				unescapeUnderscores(name)
			)}} anchor={${JSON.stringify(anchor)}} parameters={${signature}} source={${JSON.stringify(
				source
			)}} `;

			if (docstringBody.match(REGEX_PARAMSDESC)) {
				const content = docstringBody.match(REGEX_PARAMSDESC)[1];
				let { code } = await mdsvexPreprocess.markup({ content, filename });
				code = code.replace(REGEX_TIP, (_, isWarning, tipContent) => {
					// render <Tip> components that are inside parameter descriptions
					const color = isWarning ? "orange" : "green";
					return `<div
						class="course-tip ${
							color === "orange" ? "course-tip-orange" : ""
						} bg-gradient-to-br dark:bg-gradient-to-r before:border-${color}-500 dark:before:border-${color}-800 from-${color}-50 dark:from-gray-900 to-white dark:to-gray-950 border border-${color}-50 text-${color}-700 dark:text-gray-400"
					>
						${tipContent}
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
						parameterGroups.push({ title, parametersDescription: code });
					}
					svelteComponent += ` parameterGroups={${JSON.stringify(parameterGroups)}} `;
				}
			}

			svelteComponent += ` />\n`;
			return svelteComponent;
		});

		return { code: content };
	}
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

export const mdsvexPreprocess = {
	markup: async ({ content, filename }) => {
		if (filename.endsWith(".mdx")) {
			const markedKatex = {};
			// if (filename.includes("course/")) {
			// 	content = addCourseImports(content);
			// }
			content = markKatex(content, markedKatex);
			const processed = await _mdsvexPreprocess.markup({ content, filename });
			processed.code = renderKatex(processed.code, markedKatex);
			processed.code = headingWithAnchorLink(processed.code);
			processed.code = renderCode(processed.code, filename);
			return processed;
		}
		return { code: content };
	}
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
 * The mdx file contains unnecessarily espaced underscores in the docstring's name
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
	const REGEX_LATEX_DISPLAY = /\n\$\$([\s\S]+?)\$\$/g;
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
		const { tex, displayMode } = markedKatex[marker];
		const html = katex.renderToString(renderSvelteChars(tex), {
			displayMode,
			throwOnError: false
		});
		if (html.includes(`katex-error`)) {
			throw new Error(`[KaTeX] Error while parsing markdown\n ${html}`);
		}
		return `{@html ${JSON.stringify(html)}}`;
	});
}

const _mdsvexPreprocess = mdsvex({
	extensions: ["mdx"],
	highlight: {
		highlighter: function (code, lang) {
			const REGEX_CODE_INPUT = /^(>>>\s|\.\.\.\s|$)/;
			const _highlight = (code) =>
				lang && hljs.getLanguage(lang)
					? hljs.highlight(lang, code, true).value
					: hljs.highlightAuto(code).value;
			code = renderSvelteChars(code);
			const REGEX_FRAMEWORKS_SPLIT = /\s*===PT-TF-SPLIT===\s*/gm;
			if (code.match(REGEX_FRAMEWORKS_SPLIT)) {
				let [codePt, codeTf] = code.split(REGEX_FRAMEWORKS_SPLIT);
				const highlightedPt = _highlight(codePt);
				const highlightedTf = _highlight(codeTf);
				// filter out outputs if the code was generated interactively
				// `>>> for i in range(5):` becomes `for i in range(5):`
				if (codePt.match(REGEX_CODE_INPUT)) {
					codePt = codePt
						.split("\n")
						.filter((line) => line.match(REGEX_CODE_INPUT))
						.map((line) => line.slice(4))
						.join("\n");
				}
				if (codeTf.match(REGEX_CODE_INPUT)) {
					codeTf = codeTf
						.split("\n")
						.filter((line) => line.match(REGEX_CODE_INPUT))
						.map((line) => line.slice(4))
						.join("\n");
				}
				return `
	<CodeBlockFw 
		pt={{
			code: \`${codePt.replace(/\\/g, "\\\\").replace(/`/g, "\\`")}\`,
			highlighted: \`${highlightedPt.replace(/\\/g, "\\\\").replace(/`/g, "\\`")}\`
		}}
		tf={{
			code: \`${codeTf.replace(/\\/g, "\\\\").replace(/`/g, "\\`")}\`,
			highlighted: \`${highlightedTf.replace(/\\/g, "\\\\").replace(/`/g, "\\`")}\`
		}}
	/>`;
			} else {
				const highlighted = _highlight(code);
				// filter out outputs if the code was generated interactively
				// `>>> for i in range(5):` becomes `for i in range(5):`
				if (code.match(REGEX_CODE_INPUT)) {
					code = code
						.split("\n")
						.filter((line) => line.match(REGEX_CODE_INPUT))
						.map((line) => line.slice(4))
						.join("\n");
				}
				return `
	<CodeBlock 
		code={\`${code.replace(/\\/g, "\\\\").replace(/`/g, "\\`")}\`},
		highlighted={\`${highlighted.replace(/\\/g, "\\\\").replace(/`/g, "\\`")}\`}
	/>`;
			}
		}
	}
});

/**
 * Dynamically add anchor links to html heading tags
 * @param {string} code
 */
function headingWithAnchorLink(code) {
	const REGEX_HEADER = /<h([1-6]) ?(id="(.+)")?>(.*)<\/h[1-6]>/gm;
	const REGEX_CODE = /`(((?!`).)*)`/gms;
	return code.replace(REGEX_HEADER, (_, level, __, id, text) => {
		if (!id) {
			id = text
				.replace(/(.*)<a href.+>(.+)<\/a>(.*)/gm, (_, g1, g2, g3) => `${g1}${g2}${g3}`)
				.toLowerCase()
				.split(" ")
				.join("-");
		}
		return `<h${level} class="relative group">
	<a 
		id="${id}" 
		class="header-link block pr-1.5 text-lg no-hover:hidden with-hover:absolute with-hover:p-1.5 with-hover:opacity-0 with-hover:group-hover:opacity-100 with-hover:right-full" 
		href="#${id}"
	>
		<span><IconCopyLink/></span>
	</a>
	<span>
		${text.replace(REGEX_CODE, (_, group1) => `<code>${group1}</code>`)}
	</span>
</h${level}>\n`;
	});
}

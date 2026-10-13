import domUtils from "domutils";
import htmlparser2 from "htmlparser2";
import { replaceAsync, renderSvelteChars, generateTagRegex } from "./utils.js";
import { mdsvexPreprocess } from "./mdsvex/index.js";

/**
 * mdsvex prepends a page-level `<script context="module">` metadata block to everything it
 * compiles. Inside a docstring fragment it would end up as a stray inline script in the page.
 */
async function markupFragment(content, filename) {
	const result = await mdsvexPreprocess.markup({ content, filename });
	return {
		...result,
		code: result.code.replace(/<script context="module">[\s\S]*?<\/script>/, ""),
	};
}

const REGEX_PARAMSDESC = generateTagRegex("paramsdesc");
const REGEX_PARAMSGROUP = generateTagRegex("paramsgroup", true);
const REGEX_PARAMSGROUP_TITLE = generateTagRegex("paramsgrouptitle");
const REGEX_PARAMSGROUP_DESC = generateTagRegex("paramsgroupdesc");
const REGEX_RETDESC = generateTagRegex("retdesc");
const REGEX_RETTYPE = generateTagRegex("rettype");
// note: fixes a long-standing tag mismatch (python emits `yielddesc`, the old regex
// matched `yieldesc`), which silently dropped yield descriptions
const REGEX_YIELDESC = generateTagRegex("yielddesc");
const REGEX_YIELDTYPE = generateTagRegex("yieldtype");
const REGEX_RAISEDESC = generateTagRegex("raises");
const REGEX_RAISETYPE = generateTagRegex("raisederrors");
const REGEX_TIP = /<Tip( warning={true})?>(((?!<Tip( warning={true})?>).)*)<\/Tip>/gms;
const REGEX_CHANGED =
	/<(Added|Changed|Deprecated) version="([0-9.v]+)" ?\/?>((((?!<(Added|Changed|Deprecated) version="([0-9.v]+)"\/?>).)*)<\/(Added|Changed|Deprecated)>)?/gms;

/**
 * Python (doc_builder/autodoc.py) emits the `<Docstring ...metadata props...>` component
 * directly; its body carries the markdown-bearing sections (parameter descriptions,
 * return/yield/raise types & descriptions), which must be rendered with the same mdsvex
 * pipeline as the rest of the page. This preprocessor renders those sections into the
 * remaining component props and closes the component.
 */
export const docstringPreprocess = {
	markup: async ({ content, filename }) => {
		// The open tag ends at the first `>` followed by a newline: attribute values are
		// single-line JSON, which may contain `>` inside strings but never a raw newline.
		const REGEX_DOCSTRING = /<Docstring((?:(?!>\n)[\s\S])*)>\n([\s\S]*?)<\/Docstring>/g;

		content = await replaceAsync(content, REGEX_DOCSTRING, async (_, metadataAttrs, body) => {
			body = renderSvelteChars(body);

			// parameter anchors are prefixed with the object's anchor
			const anchor = metadataAttrs.match(/ anchor=\{"((?:[^"\\]|\\.)*)"\}/)?.[1] ?? "";

			let svelteComponent = `<Docstring${metadataAttrs} `;

			if (body.match(REGEX_PARAMSDESC)) {
				let paramsContent = body.match(REGEX_PARAMSDESC)[1];
				// escape }} by adding void character `&zwnj;` in between
				paramsContent = paramsContent.replace(/}}/g, "}&zwnj;}");
				let { code } = await markupFragment(paramsContent, filename);
				// render <Tip> components that are inside parameter descriptions
				code = code.replace(REGEX_TIP, (_tip, isWarning, tipContent) => {
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
				code = code.replace(
					REGEX_CHANGED,
					(_changed, componentType, version, __, descriptionContent) => {
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
					}
				);

				const result = parseRenderedParamsList(code, anchor);
				if (result) {
					svelteComponent += ` parametersDescription={${JSON.stringify(result)}} `;
				}
			}

			if (body.match(REGEX_RETDESC)) {
				const retDesc = body.match(REGEX_RETDESC)[1];
				const { code } = await markupFragment(retDesc, filename);
				svelteComponent += ` returnDescription={${JSON.stringify(code)}} `;
			}

			if (body.match(REGEX_RETTYPE)) {
				const retType = body.match(REGEX_RETTYPE)[1];
				const { code } = await markupFragment(retType, filename);
				svelteComponent += ` returnType={${JSON.stringify(code)}} `;
			}

			if (body.match(REGEX_YIELDESC)) {
				const yieldDesc = body.match(REGEX_YIELDESC)[1];
				const { code } = await markupFragment(yieldDesc, filename);
				svelteComponent += ` returnDescription={${JSON.stringify(code)}} `;
			}

			if (body.match(REGEX_YIELDTYPE)) {
				const yieldType = body.match(REGEX_YIELDTYPE)[1];
				const { code } = await markupFragment(yieldType, filename);
				svelteComponent += ` returnType={${JSON.stringify(code)}} isYield={true} `;
			}

			if (body.match(REGEX_RAISEDESC)) {
				const raiseDesc = body.match(REGEX_RAISEDESC)[1];
				const { code } = await markupFragment(raiseDesc, filename);
				svelteComponent += ` raiseDescription={${JSON.stringify(code)}} `;
			}

			if (body.match(REGEX_RAISETYPE)) {
				const raiseType = body.match(REGEX_RAISETYPE)[1];
				const { code } = await markupFragment(raiseType, filename);
				svelteComponent += ` raiseType={${JSON.stringify(code)}} `;
			}

			const parameterGroups = [];
			for (const [, groupBody] of body.matchAll(REGEX_PARAMSGROUP)) {
				const title = groupBody.match(REGEX_PARAMSGROUP_TITLE)[1];
				const groupContent = groupBody.match(REGEX_PARAMSGROUP_DESC)[1];
				const { code } = await markupFragment(groupContent, filename);
				parameterGroups.push({
					title,
					parametersDescription: parseRenderedParamsList(code, anchor) ?? [],
				});
			}
			if (parameterGroups.length) {
				svelteComponent += ` parameterGroups={${JSON.stringify(parameterGroups)}} `;
			}

			svelteComponent += ` />\n`;
			return svelteComponent;
		});

		return { code: content };
	},
};

/**
 * The parameter descriptions are authored as a markdown bullet list (`- **name** -- desc`)
 * and must be rendered as one list to keep exact markdown semantics (tight/loose lists);
 * this parses the rendered `<ul>` back into per-parameter structured data for the
 * `Docstring` component (tooltips, per-parameter anchors).
 * @param {string} code rendered html
 * @param {string} anchor the object's anchor, used as prefix for parameter anchors
 */
function parseRenderedParamsList(code, anchor) {
	const dom = htmlparser2.parseDocument(code);
	const lists = domUtils.getElementsByTagName("ul", dom);
	if (!lists.length) {
		return undefined;
	}
	const result = [];
	for (const childEl of lists[0].childNodes.filter(({ type }) => type === "tag")) {
		const nameEl = domUtils.getElementsByTagName("strong", childEl)[0];
		const name = domUtils.innerText(nameEl);
		const paramAnchor = `${anchor}.${name}`;
		let description = domUtils.getInnerHTML(childEl).trim();

		// unwrap the first paragraph so it renders inline next to the parameter name; later
		// paragraphs keep their <p> tags (stripping only the outer tags would leave a stray
		// `</p><p>` inside the rendering <span>, which breaks hydration)
		if (description.startsWith("<p>")) {
			const end = description.indexOf("</p>");
			if (end !== -1) {
				description = description.slice("<p>".length, end) + description.slice(end + "</p>".length);
			}
		}

		result.push({ anchor: paramAnchor, description, name });
	}
	return result;
}

import domUtils from "domutils";
import htmlparser2 from "htmlparser2";
import { replaceAsync, renderSvelteChars, generateTagRegex } from "./utils.js";
import { mdsvexPreprocess } from "./mdsvex/index.js";

// Preprocessor that converts markdown into Docstring
// svelte component using mdsvexPreprocess
export const docstringPreprocess = {
	markup: async ({ content, filename }) => {
		const REGEX_DOCSTRING = generateTagRegex("docstring", true);
		const REGEX_NAME = generateTagRegex("name");
		const REGEX_ANCHOR = generateTagRegex("anchor");
		const REGEX_SIGNATURE = generateTagRegex("parameters");
		const REGEX_PARAMSDESC = generateTagRegex("paramsdesc");
		const REGEX_PARAMSGROUPS = generateTagRegex("paramgroups");
		const REGEX_RETDESC = generateTagRegex("retdesc");
		const REGEX_RETTYPE = generateTagRegex("rettype");
		const REGEX_YIELDESC = generateTagRegex("yieldesc");
		const REGEX_YIELDTYPE = generateTagRegex("yieldtype");
		const REGEX_RAISEDESC = generateTagRegex("raises");
		const REGEX_RAISETYPE = generateTagRegex("raisederrors");
		const REGEX_SOURCE = generateTagRegex("source");
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

/**
 * The mdx file contains unnecessarily escaped underscores in the docstring's name
 */
function unescapeUnderscores(content) {
	return content.replace(/\\_/g, "_");
}

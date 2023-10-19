import { replaceAsync, generateTagRegex } from "./utils.js";

// Preprocessor that converts markdown into InferenceApi
// svelte component using mdsvexPreprocess
export const inferenceSnippetPreprocess = {
	markup: async ({ content }) => {
		const REGEX_FRAMEWORKCONTENT = generateTagRegex("inferencesnippet", true);
		const REGEX_PYTHON = generateTagRegex("python");
		const REGEX_JS = generateTagRegex("js");
		const REGEX_CURL = generateTagRegex("curl");
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

import { replaceAsync, generateTagRegex } from "./utils.js";

// Preprocessor that converts markdown into TokenizersLanguageContent
// svelte component using mdsvexPreprocess
export const tokenizersLangPreprocess = {
	markup: async ({ content }) => {
		const REGEX_FRAMEWORKCONTENT = generateTagRegex("tokenizerslangcontent", true);
		const REGEX_PYTHON = generateTagRegex("python");
		const RGEX_RUST = generateTagRegex("rust");
		const REGEX_NODE = generateTagRegex("node");
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

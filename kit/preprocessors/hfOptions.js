import { replaceAsync, generateTagRegexWithId } from "./utils.js";

// Preprocessor that converts markdown into HfOptions
// svelte component using mdsvexPreprocess
export const hfOptionsPreprocess = {
	markup: async ({ content }) => {
		const REGEX_HF_OPTIONS = generateTagRegexWithId("hfoptions", true);
		const REGEX_HF_OPTION = generateTagRegexWithId("hfoption", true);
		content = await replaceAsync(content, REGEX_HF_OPTIONS, async (_, id, hfOptionsContent) => {
			const options = [];
			hfOptionsContent = await replaceAsync(
				hfOptionsContent,
				REGEX_HF_OPTION,
				async (__, option, hfOptionContent) => {
					options.push(option);
					return `<HfOption id="${id}" option="${option}">\n\n${hfOptionContent}\n\n</HfOption>`;
				}
			);
			return `<HfOptions id="${id}" options={${JSON.stringify(
				options
			)}}>\n${hfOptionsContent}\n</HfOptions>`;
		});
		return { code: content };
	},
};

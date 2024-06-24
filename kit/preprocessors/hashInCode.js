import { replaceAsync } from "./utils.js";

// Preprocessor that converts `#` char inside code/codeblocks into its html5 entity `&amp;num;`
// otherwise, an extra new space was being rendered
export const hashInCodePreprocess = {
	markup: async ({ content }) => {
		const REGEX_CODE_BLOCK = /```.*?```/gs;
		const REGEX_INLINE_CODE = /`.*?`/g;
		content = await replaceAsync(content, REGEX_CODE_BLOCK, async (codeContent) => {
			return codeContent.replaceAll("#", "&amp;num;");
		});
		content = await replaceAsync(content, REGEX_INLINE_CODE, async (codeContent) => {
			return codeContent.replaceAll("#", "&amp;num;");
		});
		return { code: content };
	},
};

import { replaceAsync, generateTagRegex } from "./utils.js";

// Preprocessor that converts markdown into FrameworkContent
// svelte component using mdsvexPreprocess
export const frameworkcontentPreprocess = {
	markup: async ({ content }) => {
		const REGEX_FRAMEWORKCONTENT = generateTagRegex("frameworkcontent", true);
		const REGEX_PYTORCH = generateTagRegex("pt");
		const REGEX_TENSORFLOW = generateTagRegex("tf");
		const REGEX_JAX = generateTagRegex("jax");

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

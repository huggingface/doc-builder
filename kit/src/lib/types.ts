export type Group = "group1" | "group2";

export type Framework = "pytorch" | "tensorflow" | "jax";

export type TokenizersLanguage = "python" | "rust" | "node";

export type CourseFramework = "pt" | "tf";

export type InferenceSnippetLang = "python" | "js" | "curl";

export interface Pipeline {
	name: string;
	subtasks?: { type: string; name: string }[];
	modality: string;
	color: string;
	hideInModels?: boolean;
	hideInDatasets?: boolean;
}

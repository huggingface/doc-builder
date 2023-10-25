import type { Writable } from "svelte/store";
import { writable } from "svelte/store";
import type { Group, Framework, InferenceSnippetLang, TokenizersLanguage } from "./types";

// used for CodeBlockFw.svelte
const groups: Record<string, Writable<Group>> = {};
export function getGroupStore(key: string): Writable<Group> {
	if (!groups[key]) {
		groups[key] = writable<Group>("group1");
	}
	return groups[key];
}

// used for FrameworkContent.svelte
export enum AccordianState {
	OPEN = "OPEN",
	CLOSED = "CLOSED",
	HASHASHLINK = "HASHASHLINK",
}
const frameworks: Partial<Record<Framework, Writable<AccordianState>>> = {};
export function getFrameworkStore(key: Framework): Writable<AccordianState> {
	return (frameworks[key] = frameworks[key] || writable<AccordianState>(AccordianState.OPEN));
}

// used for Question.svelte
export const answers = writable<{ [key: string]: { correct: boolean } }>({});

// used for InferenceApi.svelte
export const selectedInferenceLang = writable<InferenceSnippetLang>("python");

// used for TokenizersLanguageContent.svelte
export const selectedTokenizersLang = writable<TokenizersLanguage>("python");

// used for HfOptions.svelte
export const selectedHfOptions = writable<Record<string, string>>({});

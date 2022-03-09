import type { Writable } from "svelte/store";
import { writable } from "svelte/store";
import type { Group, Framework } from "./types";

// used for CodeBlockFw.svelte
const groups: Record<string, Writable<Group>> = {};
export function getGroupStore(key: string): Writable<Group> {
	if (!groups[key]) {
		groups[key] = writable<Group>("group1");
	}
	return groups[key];
}

// used for FrameworkContent.svelte
const frameworks: { [key in Framework]?: Writable<boolean> } = {};
export function getFrameworkStore(key: Framework): Writable<boolean> {
	if (!frameworks[key]) {
		frameworks[key] = writable<boolean>(false);
	}
	return frameworks[key];
}

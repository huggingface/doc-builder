import { writable } from "svelte/store";
import type { Group } from "./types";

export const group = writable<Group>("group1");

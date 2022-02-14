import { writable } from "svelte/store";
import type { Framework } from "./types";

export const fw = writable<Framework>("pt");

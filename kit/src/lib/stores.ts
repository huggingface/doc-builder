import type { Writable } from "svelte/store";
import { writable } from "svelte/store";
import type { Group } from "./types";

const groups: Record<string, Writable<Group>> = {};

export function getGroupStore(key: string): Writable<Group>{
    if(!groups[key]){
        groups[key] = writable<Group>("group1");
    }
    return groups[key];
}

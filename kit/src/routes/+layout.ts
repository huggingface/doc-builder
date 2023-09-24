import { base } from "$app/paths";

// This can be false if you're using a fallback (i.e. SPA mode)
export const prerender = true;

/** @type {import('./$types').PageLoad} */
export async function load({ fetch }) {
    if (!import.meta.env.DEV) {
        return {};
    }
    const toc = await fetch(base + "/endpoints/toc");
    return {
        toc: await toc.json()
    };
}
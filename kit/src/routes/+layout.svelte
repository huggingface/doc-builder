
<script lang="ts">
	import { onMount } from "svelte";
	import { afterNavigate } from "$app/navigation";
	import { base } from "$app/paths";
	import { getHfDocFullPath } from "$lib/hfDocPaths.js";
	import type { RawChapter } from "./endpoints/toc/+server";
	import "../app.css";

	export let data;
	$: toc = (data.toc ?? []) as RawChapter[];

	/**
	 * Shorthand hf doc links (e.g. /docs/lib/page) should partial-load like
	 * internal routes while keeping the shorthand URL in the address bar —
	 * the behavior of the old `svelteKitCustomClient` fork.
	 * SvelteKit treats URLs that don't start with the app's base path as
	 * external before it consults the `reroute` hook (src/hooks.js), so:
	 *  1. on click, momentarily expand the anchor's pathname to the full path
	 *     so SvelteKit's own click handler resolves it as an internal route,
	 *  2. after the navigation completes, restore the shorthand URL in the
	 *     history entry.
	 * Caveat: going back/forward onto a shorthand history entry falls back to
	 * a full page load (the server serves the same page at shorthand URLs).
	 */
	let pendingShorthand: { href: string; fullPath: string } | null = null;

	onMount(() => {
		const canonicalizeDocLinks = (event: MouseEvent) => {
			// same conditions as SvelteKit's click handler: plain left-clicks only,
			// so that e.g. cmd/ctrl-click opens the shorthand URL in a new tab
			if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
				return;
			}
			const anchor = (event.target as Element | null)?.closest("a");
			if (!anchor || anchor.origin !== location.origin || anchor.target) return;
			const shorthandPathname = anchor.pathname;
			const fullPath = getHfDocFullPath(shorthandPathname);
			if (fullPath && fullPath !== shorthandPathname) {
				pendingShorthand = { href: anchor.href, fullPath };
				anchor.pathname = fullPath;
				// restore the DOM link once SvelteKit's handler has read it
				setTimeout(() => {
					anchor.pathname = shorthandPathname;
				});
			}
		};
		document.addEventListener("click", canonicalizeDocLinks, { capture: true });
		return () => document.removeEventListener("click", canonicalizeDocLinks, { capture: true });
	});

	afterNavigate((navigation) => {
		if (
			pendingShorthand &&
			navigation.type === "link" &&
			navigation.to?.url.pathname === pendingShorthand.fullPath
		) {
			history.replaceState(history.state, "", pendingShorthand.href);
		}
		pendingShorthand = null;
	});
</script>

{#if !import.meta.env.DEV}
	<slot />
{:else}
	<style>
		body,
		html {
			padding: 0;
			margin: 0;
		}
	</style>
	<div
		class="flex"
	>
		<div class="w-[270px] 2xl:w-[300px] hidden md:block border-r-2 shrink-0">
			<ul class="pt-2 flex flex-col pl-3 w-full">
				{#each toc as section}
					{#if section.local}
						<a
							role="navigation"
							class="block text-gray-500 pr-2 hover:text-black dark:hover:text-gray-300 py-1"
							href="{base}/{section.local.replace(/\bindex$/, '')}">{section.title}</a
						>
					{:else}
						<span
						role="navigation"
						class="opacity-50 text-lg block text-gray-500 pr-2 hover:text-black dark:hover:text-gray-300 py-1"
						>{section.title}</span>
					{/if}
				{/each}
			</ul>
		</div>
		<div class="px-4 pt-3 grow">
			<div class="prose prose-doc dark:prose-light max-w-4xl mx-auto break-words relative">
				<slot />
			</div>
		</div>
		<div class="w-[270px] 2xl:w-[305px] hidden lg:block border-l-2 shrink-0 opacity-50 p-4">
			Sub side menu
		</div>
	</div>
{/if}

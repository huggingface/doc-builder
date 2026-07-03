
<script lang="ts">
	import { onMount } from "svelte";
	import { base } from "$app/paths";
	import { getHfDocFullPath } from "$lib/hfDocPaths.js";
	import type { RawChapter } from "./endpoints/toc/+server";
	import "../app.css";

	export let data;
	$: toc = (data.toc ?? []) as RawChapter[];

	onMount(() => {
		// Expand shorthand hf doc links (e.g. /docs/lib/page) to the full path
		// before SvelteKit's own click handler reads the anchor, so they are
		// treated as internal routes (partial loading instead of a full reload).
		// Complements the `reroute` hook (src/hooks.js), which is not consulted
		// for URLs that don't start with the app's base path.
		const canonicalizeDocLinks = (event: MouseEvent) => {
			const anchor = (event.target as Element | null)?.closest("a");
			if (!anchor || anchor.origin !== location.origin) return;
			const fullPath = getHfDocFullPath(anchor.pathname);
			if (fullPath && fullPath !== anchor.pathname) {
				anchor.pathname = fullPath;
			}
		};
		document.addEventListener("click", canonicalizeDocLinks, { capture: true });
		return () => document.removeEventListener("click", canonicalizeDocLinks, { capture: true });
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

<script context="module" lang="ts">
	import { base } from "$app/paths";

	export async function load(input: LoadInput) {
		if (prerendering || !import.meta.env.DEV) {
			return {};
		}

		const toc = await input.fetch(base + "/endpoints/toc");

		return {
			props: {
				toc: await toc.json()
			}
		};
	}
</script>

<script lang="ts">
	import type { LoadInput } from "@sveltejs/kit";
	import type { RawChapter } from "./endpoints/toc";
	import { prerendering } from "$app/env";
	import "../app.css";

	export let toc: RawChapter[];
</script>

{#if prerendering || !import.meta.env.DEV}
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
		class="flex space-x-4"
	>
		<div class="border-r-2">
			<ul class="pt-2 flex flex-col pl-3">
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
		<div class="px-4 pt-3">
			<div class="prose prose-doc dark:prose-light max-w-4xl mx-auto break-words relative">
				<slot />
			</div>
		</div>
	</div>
{/if}

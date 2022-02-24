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
	import { prerendering } from "$app/env";
	import "../app.css";

	export let toc: Array<{
		sections: Array<
			{ title: string } & ({ local: string } | { sections: { title: string; local: string }[] })
		>;
		title: string;
	}>;
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
		style="width: 100vh; height: 100vh; margin: 0; padding: 0; display: flex; flex-direction: row"
	>
		<aside
			style="width: 270px; min-width: 270px; max-width: 270px; border-right: 1px solid gray; height: 100vh; position: fixed; overflow-y: auto; display: flex; flex-direction: column"
		>
			<ul class="pt-2 flex flex-col pl-3">
				{#each toc as section}
					<h3
						class="flex group-hover:after:content-['▶'] after:absolute after:right-4 after:text-gray-500 after:transition after:duration-100 after:ease-in after:transform after:rotate-90"
					>
						{section.title}
					</h3>
					<div class="pl-4">
						{#each section.sections as subsection}
							{#if "sections" in subsection}
								<h3
									class="flex group-hover:after:content-['▶'] after:absolute after:right-4 after:text-gray-500 after:transition after:duration-100 after:ease-in after:transform after:rotate-90"
								>
									{subsection.title}
								</h3>

								<ul class="pt-2 flex flex-col pl-3">
									{#each subsection.sections as finalsection}
										<a
											role="navigation"
											class="block text-gray-500 pr-2 hover:text-black dark:hover:text-gray-300 py-1 transform transition-all hover:translate-x-px first:mt-1 last:mb-4 pl-2 ml-2"
											href="{base}/{finalsection.local.replace(/\bindex$/, '')}"
											>{finalsection.title}</a
										>
									{/each}
								</ul>
							{:else}
								<a
									role="navigation"
									class="block text-gray-500 pr-2 hover:text-black dark:hover:text-gray-300 py-1 transform transition-all hover:translate-x-px first:mt-1 last:mb-4 pl-2 ml-2"
									href="{base}/{subsection.local.replace(/\bindex$/, '')}">{subsection.title}</a
								>
							{/if}
						{/each}
					</div>
				{/each}
			</ul>
		</aside>
		<div style="margin-left: 270px;" class="px-4 pt-3">
			<div class="prose prose-doc dark:prose-light max-w-4xl mx-auto break-words relative">
				<slot />
			</div>
		</div>
	</div>
{/if}

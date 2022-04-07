<script lang="ts">
	import type { InferenceSnippetLang } from "./types";
	import { selectedInferenceLang } from "./stores";
	import IconPython from "./IconPython.svelte";
	import IconJs from "./IconJs.svelte";
	import IconCurl from "./IconCurl.svelte";

	const LANGUAGES_CONFIG: {
		id: InferenceSnippetLang;
		icon: typeof IconPython;
		label: string;
	}[] = [
		{
			id: "python",
			icon: IconPython,
			label: "Python"
		},
		{
			id: "js",
			icon: IconJs,
			label: "JavaScript"
		},
		{
			id: "curl",
			icon: IconCurl,
			label: "cURL"
		}
	];

	export let python = false;
	export let js = false;
	export let curl = false;
</script>

<form class="px-4 py-1.5 flex flex-wrap items-center justify-between border-b border-gray-100">
	<ul class="flex space-x-2 items-center my-1.5 mr-8 h-7">
		{#each LANGUAGES_CONFIG as language}
			<li
				class="flex items-center border rounded-lg px-1.5 py-1 leading-none select-none text-smd
                {$selectedInferenceLang === language.id
					? 'border-gray-800 bg-black dark:bg-gray-700 text-white'
					: 'text-gray-500 cursor-pointer opacity-90 hover:text-gray-700 dark:hover:text-gray-200 hover:shadow-sm'}"
				on:click={() => ($selectedInferenceLang = language.id)}
			>
				<svelte:component this={language.icon} classNames="mr-1.5" />
				{language.label}
			</li>
		{/each}
	</ul>
</form>
{#if python && $selectedInferenceLang === "python"}
	<slot name="python" />
{/if}
{#if js && $selectedInferenceLang === "js"}
	<slot name="js" />
{/if}
{#if curl && $selectedInferenceLang === "curl"}
	<slot name="curl" />
{/if}

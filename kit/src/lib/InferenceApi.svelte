<script lang="ts">
	import type { InferenceSnippetLang } from "./types";
	import { onMount } from "svelte";
	import { selectedInferenceLang } from "./stores";
	import { getQueryParamValue, updateQueryParamAndReplaceHistory } from "./utils";
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
			label: "Python",
		},
		{
			id: "js",
			icon: IconJs,
			label: "JavaScript",
		},
		{
			id: "curl",
			icon: IconCurl,
			label: "cURL",
		},
	];

	export let python = false;
	export let js = false;
	export let curl = false;

	const snippetExists = { python, js, curl };
	const queryParamKey = "code";

	function updateSelectedOption(lang: InferenceSnippetLang) {
		$selectedInferenceLang = lang;
		updateQueryParamAndReplaceHistory(queryParamKey, lang);
	}

	onMount(() => {
		const valueFromQueryParams = getQueryParamValue(queryParamKey) as InferenceSnippetLang | null;
		const validOptions = ["python", "js", "curl"] as InferenceSnippetLang[];
		if (valueFromQueryParams && validOptions.includes(valueFromQueryParams)) {
			$selectedInferenceLang = valueFromQueryParams;
		}
	});
</script>

<div class="flex space-x-2 items-center my-1.5 mr-8 h-7 !pl-0 -mx-3 md:mx-0">
	{#each LANGUAGES_CONFIG.filter((c) => snippetExists[c.id]) as language}
		<div
			class="flex items-center border rounded-lg px-1.5 py-1 leading-none select-none text-smd
			{$selectedInferenceLang === language.id
				? 'border-gray-800 bg-black dark:bg-gray-700 text-white'
				: 'text-gray-500 cursor-pointer opacity-90 hover:text-gray-700 dark:hover:text-gray-200 hover:shadow-sm'}"
			on:click={() => updateSelectedOption(language.id)}
		>
			<svelte:component this={language.icon} classNames="mr-1.5" />
			{language.label}
		</div>
	{/each}
</div>
<div class="language-select">
	{#if python && $selectedInferenceLang === "python"}
		<slot name="python" />
	{/if}
	{#if js && $selectedInferenceLang === "js"}
		<slot name="js" />
	{/if}
	{#if curl && $selectedInferenceLang === "curl"}
		<slot name="curl" />
	{/if}
</div>

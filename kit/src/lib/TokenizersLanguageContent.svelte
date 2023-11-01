<script lang="ts">
	import type { TokenizersLanguage } from "./types";
	import { onMount } from "svelte";
	import { selectedTokenizersLang } from "./stores";
	import { getQueryParamValue, updateQueryParamAndReplaceHistory } from "./utils";
	import IconPython from "./IconPython.svelte";
	import IconRust from "./IconRust.svelte";
	import IconNode from "./IconNode.svelte";

	const LANGUAGES_CONFIG: {
		id: TokenizersLanguage;
		icon: typeof IconPython;
		label: string;
	}[] = [
		{
			id: "python",
			icon: IconPython,
			label: "Python",
		},
		{
			id: "rust",
			icon: IconRust,
			label: "Rust",
		},
		{
			id: "node",
			icon: IconNode,
			label: "Node",
		},
	];
	const queryParamKey = "code";

	export let python = false;
	export let rust = false;
	export let node = false;

	function updateSelectedOption(lang: TokenizersLanguage) {
		$selectedTokenizersLang = lang;
		updateQueryParamAndReplaceHistory(queryParamKey, lang);
	}

	onMount(() => {
		const valueFromQueryParams = getQueryParamValue(queryParamKey) as TokenizersLanguage | null;
		const validOptions = ["python", "js", "curl"] as TokenizersLanguage[];
		if (valueFromQueryParams && validOptions.includes(valueFromQueryParams)) {
			$selectedTokenizersLang = valueFromQueryParams;
		}
	});
</script>

<div class="flex space-x-2 items-center my-1.5 mr-8 h-7 !pl-0 -mx-3 md:mx-0">
	{#each LANGUAGES_CONFIG as language}
		<div
			class="flex items-center border rounded-lg px-1.5 py-1 leading-none select-none text-smd
			{$selectedTokenizersLang === language.id
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
	{#if python && $selectedTokenizersLang === "python"}
		<slot name="python" />
	{/if}
	{#if rust && $selectedTokenizersLang === "rust"}
		<slot name="rust" />
	{/if}
	{#if node && $selectedTokenizersLang === "node"}
		<slot name="node" />
	{/if}
</div>

<script lang="ts">
	import { onMount } from "svelte";
	import { selectedHfOptions } from "./stores";
	import { getQueryParamValue, updateQueryParamAndReplaceHistory } from "./utils";

	export let id: string;
	export let options: string[];

	$selectedHfOptions[id] = options[0];

	function updateSelectedOption(option: string) {
		$selectedHfOptions[id] = option;
		updateQueryParamAndReplaceHistory(id, option);
	}

	onMount(() => {
		const valueFromQueryParams = getQueryParamValue(id);
		if (valueFromQueryParams && options.includes(valueFromQueryParams)) {
			$selectedHfOptions[id] = valueFromQueryParams;
		}
	});
</script>

<div class="flex space-x-2 items-center my-1.5 mr-8 h-7 !pl-0 -mx-3 md:mx-0">
	{#each options as option}
		<div
			class="flex items-center border rounded-lg px-1.5 py-1 leading-none select-none text-smd
			{$selectedHfOptions[id] === option
				? 'border-gray-800 bg-black dark:bg-gray-700 text-white'
				: 'text-gray-500 cursor-pointer opacity-90 hover:text-gray-700 dark:hover:text-gray-200 hover:shadow-sm'}"
			on:click={() => updateSelectedOption(option)}
		>
			{option}
		</div>
	{/each}
</div>

<div class="language-select">
	<slot />
</div>

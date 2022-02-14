<script lang="ts">
	import { onDestroy } from "svelte";
	import { copyToClipboard } from "./copyToClipboard";

	import IconCopy from "./IconCopy.svelte";
	import Tooltip from "./Tooltip.svelte";

	export let classNames = "";
	export let label = "";
	export let noText = false;
	export let style: "button" | "text" = "text";
	export let value: string;

	let isSuccess = false;
	let timeout: any;

	$: text = `Copy ${label} to clipboard`;

	onDestroy(() => {
		if (timeout) {
			clearTimeout(timeout);
		}
	});

	function handleClick() {
		copyToClipboard(value);
		isSuccess = true;
		if (timeout) {
			clearTimeout(timeout);
		}
		timeout = setTimeout(() => {
			isSuccess = false;
		}, 1000);
	}
</script>

<button
	class="inline-flex items-center relative text-sm focus:text-green-500  cursor-pointer focus:outline-none
		{classNames}
		{style === 'text' ? 'mx-0.5' : 'btn'}
		{!isSuccess && style === 'text' ? 'text-gray-600' : ''}
		{isSuccess ? 'text-green-500' : ''}
	"
	on:click={handleClick}
	title={text}
	type="button"
>
	<IconCopy />
	{#if !noText}
		<span class="ml-1.5 {style === 'text' ? 'underline' : ''}">
			{text}
		</span>
	{/if}
	<Tooltip classNames={isSuccess ? "opacity-100" : "opacity-0"} />
</button>

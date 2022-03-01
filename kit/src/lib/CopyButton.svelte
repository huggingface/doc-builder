<script lang="ts">
	import { onDestroy } from "svelte";
	import { copyToClipboard } from "./copyToClipboard";

	import IconCopy from "./IconCopy.svelte";
	import Tooltip from "./Tooltip.svelte";

	export let classNames = "";
	export let label = "";
	export let style: "button" | "button-clear" | "text" = "text";
	export let title = "";
	export let value: string;

	let isSuccess = false;
	let timeout: any;

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
		{style === 'text' ? 'mx-0.5' : ''}
		{style === 'button' ? 'btn' : ''}
		{style === 'button-clear' ? 'py-1 px-2 border rounded-lg shadow-sm' : ''}
		{!isSuccess && ['button-clear', 'text'].includes(style) ? 'text-gray-600' : ''}
		{isSuccess ? 'text-green-500' : ''}
	"
	on:click={handleClick}
	title={title || label || "Copy to clipboard"}
	type="button"
>
	<IconCopy />
	<Tooltip classNames={isSuccess ? "opacity-100" : "opacity-0"} />
</button>

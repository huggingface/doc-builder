<script lang="ts">
	import { getGroupStore } from "./stores";
	import CopyButton from "./CopyButton.svelte";
	import FrameworkSwitch from "./FrameworkSwitch.svelte";

	export let group1: { id: string; code: string; highlighted: string };
	export let group2: { id: string; code: string; highlighted: string };

	const ids = [group1.id, group2.id];
	const storeKey = ids.join("-");
	const group = getGroupStore(storeKey);

	let hideCopyButton = true;

	function handleMouseOver() {
		hideCopyButton = false;
	}
	function handleMouseOut() {
		hideCopyButton = true;
	}
</script>

<div
	class="code-block relative"
	on:mouseover={handleMouseOver}
	on:focus={handleMouseOver}
	on:mouseout={handleMouseOut}
	on:focus={handleMouseOut}
>
	{#if $group === "group1"}
		<div class="absolute top-2.5 right-4">
			<CopyButton
				classNames="transition duration-200 ease-in-out {hideCopyButton && 'opacity-0'}"
				title="Copy code excerpt to clipboard"
				value={group1.code}
			/>
		</div>
		<pre><FrameworkSwitch {ids} />{@html group1.highlighted}</pre>
	{:else}
		<div class="absolute top-2.5 right-4">
			<CopyButton
				classNames="transition duration-200 ease-in-out {hideCopyButton && 'opacity-0'}"
				title="Copy code excerpt to clipboard"
				value={group2.code}
			/>
		</div>
		<pre><FrameworkSwitch {ids} />{@html group2.highlighted}</pre>
	{/if}
</div>

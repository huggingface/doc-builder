<script lang="ts">
	import { getGroupStore } from "./stores";
	import CopyButton from "./CopyButton.svelte";
	import FrameworkSwitch from "./FrameworkSwitch.svelte";

	interface Props {
		group1: { id: string; code: string; highlighted: string };
		group2: { id: string; code: string; highlighted: string };
		lang?: string;
		wrap?: boolean;
	}

	let { group1, group2, lang = "", wrap = false }: Props = $props();

	const ids = [group1.id, group2.id];
	const storeKey = ids.join("-");
	const group = getGroupStore(storeKey);

	let hideCopyButton = $state(true);

	function handleMouseOver() {
		hideCopyButton = false;
	}
	function handleMouseOut() {
		hideCopyButton = true;
	}
</script>

<div
	class="code-block relative"
	onmouseover={handleMouseOver}
	onfocus={() => {
		// preserved from the svelte 4 version, which bound focus to both handlers
		handleMouseOver();
		handleMouseOut();
	}}
	onmouseout={handleMouseOut}
>
	{#if $group === "group1"}
		<div class="absolute top-2.5 right-4">
			<CopyButton
				classNames="transition duration-200 ease-in-out {hideCopyButton && 'opacity-0'}"
				title="Copy code excerpt to clipboard"
				value={group1.code}
			/>
		</div>
		<pre
			class="{lang ? `language-${lang}` : ''} {wrap ? 'whitespace-pre-wrap' : ''}"><FrameworkSwitch
				{ids}
			/>{@html group1.highlighted}</pre>
	{:else}
		<div class="absolute top-2.5 right-4">
			<CopyButton
				classNames="transition duration-200 ease-in-out {hideCopyButton && 'opacity-0'}"
				title="Copy code excerpt to clipboard"
				value={group2.code}
			/>
		</div>
		<pre
			class="{lang ? `language-${lang}` : ''} {wrap ? 'whitespace-pre-wrap' : ''}"><FrameworkSwitch
				{ids}
			/>{@html group2.highlighted}</pre>
	{/if}
</div>

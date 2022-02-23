<script lang="ts">
	import { fw } from "./stores";
	import CopyButton from "./CopyButton.svelte";
	import FrameworkSwitch from "./FrameworkSwitch.svelte";

	export let pt: { code: string; highlighted: string };
	export let tf: { code: string; highlighted: string };

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
	on:blur={handleMouseOut}
>
	{#if $fw === "pt"}
		<div class="absolute top-2.5 right-4">
			<CopyButton
				classNames="transition duration-200 ease-in-out {hideCopyButton && 'opacity-0'}"
				title="Copy code excerpt to clipboard"
				value={pt.code}
			/>
		</div>
		<pre><FrameworkSwitch />{@html pt.highlighted}</pre>
	{:else}
		<div class="absolute top-2.5 right-4">
			<CopyButton
				classNames="transition duration-200 ease-in-out {hideCopyButton && 'opacity-0'}"
				title="Copy code excerpt to clipboard"
				value={tf.code}
			/>
		</div>
		<pre><FrameworkSwitch />{@html tf.highlighted}</pre>
	{/if}
</div>

<script lang="ts">
	import TokenizersLanguageContentBlock from "./TokenizersLanguageContentBlock.svelte";
	export let python = false;
	export let rust = false;
	export let node = false;
</script>

<div class="space-y-10 py-6 2xl:py-8 2xl:-mx-4">
	{#if python}
		<TokenizersLanguageContentBlock language="python">
			<slot name="python" />
		</TokenizersLanguageContentBlock>
	{/if}
	{#if rust}
		<TokenizersLanguageContentBlock language="rust">
			<slot name="rust" />
		</TokenizersLanguageContentBlock>
	{/if}
	{#if node}
		<TokenizersLanguageContentBlock language="node">
			<slot name="node" />
		</TokenizersLanguageContentBlock>
	{/if}
</div>

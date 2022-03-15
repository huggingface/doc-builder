<script lang="ts">
	import FrameworkContentBlock from "./FrameworkContentBlock.svelte";
	export let pytorch = false;
	export let tensorflow = false;
	export let jax = false;
</script>

<div class="space-y-10 py-6 2xl:py-8 2xl:-mx-4">
	{#if pytorch}
		<FrameworkContentBlock framework="pytorch">
			<slot name="pytorch" />
		</FrameworkContentBlock>
	{/if}
	{#if tensorflow}
		<FrameworkContentBlock framework="tensorflow">
			<slot name="tensorflow" />
		</FrameworkContentBlock>
	{/if}
	{#if jax}
		<FrameworkContentBlock framework="jax">
			<slot name="jax" />
		</FrameworkContentBlock>
	{/if}
</div>

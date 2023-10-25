<script lang="ts">
	import { selectedHfOptions } from "./stores";

	export let id: string;
	export let option: string;
</script>

{#if $selectedHfOptions[id] === option}
	<slot />
{/if}

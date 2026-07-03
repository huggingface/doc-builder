<script lang="ts">
	import { selectedHfOptions } from "./stores";

	interface Props {
		id: string;
		option: string;
		children?: import("svelte").Snippet;
	}

	let { id, option, children }: Props = $props();
</script>

{#if $selectedHfOptions[id] === option}
	{@render children?.()}
{/if}

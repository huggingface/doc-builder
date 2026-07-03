<script lang="ts">
	import Tip from "./Tip.svelte";

	interface Props {
		version: string;
		children?: import("svelte").Snippet;
	}

	let { version, children }: Props = $props();
</script>

<Tip>
	<p class="font-medium">Added in {version}</p>
	{@render children?.()}
</Tip>

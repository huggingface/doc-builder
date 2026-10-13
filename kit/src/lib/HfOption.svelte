<script lang="ts">
	import { selectedHfOptions } from "./stores";

	interface Props {
		id: string;
		option: string;
		children?: import("svelte").Snippet;
	}

	let { id, option, children }: Props = $props();
</script>

<!-- Every option is in the server-rendered HTML; inactive ones are only hidden. -->
<div hidden={$selectedHfOptions[id] !== option}>
	{@render children?.()}
</div>

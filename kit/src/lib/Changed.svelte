<script lang="ts">
	import Tip from "./Tip.svelte";

	export let version: string;
</script>

<Tip>
	<p class="font-medium">Changed in {version}</p>
	<slot />
</Tip>

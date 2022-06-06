<script lang="ts">
	import Tip from "./Tip.svelte";

	export let version: string;
</script>

<Tip>
	<p class="font-medium">Added in {version}</p>
	<slot />
</Tip>

<script lang="ts">
	import Tip from "./Tip.svelte";

	export let version: string;
</script>

<Tip warning>
	<p class="font-medium">Deprecated in {version}</p>
	<slot />
</Tip>

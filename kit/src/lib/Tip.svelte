<script lang="ts">
	interface IconData {
		paths: string[];
	}

	export let warning = false;
</script>

<blockquote class={warning ? "warning" : "tip"}>
	<slot />
</blockquote>

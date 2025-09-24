<script>
	export let warning = false;
</script>

<blockquote class={warning ? "warning" : "tip"}>
	<slot />
</blockquote>

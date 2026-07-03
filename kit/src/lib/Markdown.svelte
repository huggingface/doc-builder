<script lang="ts">
	interface Props {
		children?: import("svelte").Snippet;
	}

	let { children }: Props = $props();
</script>

<!-- used for FrameworkContent.svelte as a slot for markdown -->
{@render children?.()}

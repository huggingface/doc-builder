<script lang="ts">
	import { onMount } from "svelte";
	import mermaid from "mermaid";

	export let code = "";
	export let classNames = "";

	let container: HTMLDivElement;
	let chartId: string;

	onMount(async () => {
		// Generate a unique ID for this chart
		chartId = `mermaid-${Math.random().toString(36).substr(2, 9)}`;

		// Initialize mermaid with default configuration
		mermaid.initialize({
			startOnLoad: false,
			theme: "default",
			securityLevel: "sandbox",
			fontFamily: "inherit",
		});

		try {
			// Render the mermaid diagram
			const { svg } = await mermaid.render(chartId, decodeURIComponent(atob(code)));
			if (container) {
				container.innerHTML = svg;
			}
		} catch (error) {
			console.error("Error rendering mermaid chart:", error);
			if (container) {
				const errorMessage = error instanceof Error ? error.message : String(error);
				container.innerHTML = `<div class="text-red-500 p-4 border border-red-300 rounded">
					<strong>Error rendering mermaid chart:</strong><br>
					<code class="text-sm">${errorMessage}</code>
				</div>`;
			}
		}
	});
</script>

<div bind:this={container} class="mermaid-chart {classNames}" style="text-align: center;"></div>

<style>
	:global(.mermaid-chart svg) {
		max-width: 100%;
		height: auto;
	}
</style>

<script lang="ts">
	import DocNotebookDropdown from "./DocNotebookDropdown.svelte";

	export let chapter: number;
	export let notebooks: { label: string; value: string }[] = [];
	export let classNames = "";
	export let askForHelpUrl = `https://discuss.huggingface.co/t/chapter-${chapter}-questions`;
</script>

<DocNotebookDropdown options={notebooks} {classNames}>
	<svelte:fragment slot="alwaysVisible">
		<a href={askForHelpUrl} target="_blank">
			<img
				alt="Ask a Question"
				class="!m-0"
				src="https://img.shields.io/badge/Ask%20a%20question-ffcb4c.svg?logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgLTEgMTA0IDEwNiI+PGRlZnM+PHN0eWxlPi5jbHMtMXtmaWxsOiMyMzFmMjA7fS5jbHMtMntmaWxsOiNmZmY5YWU7fS5jbHMtM3tmaWxsOiMwMGFlZWY7fS5jbHMtNHtmaWxsOiMwMGE5NGY7fS5jbHMtNXtmaWxsOiNmMTVkMjI7fS5jbHMtNntmaWxsOiNlMzFiMjM7fTwvc3R5bGU+PC9kZWZzPjx0aXRsZT5EaXNjb3Vyc2VfbG9nbzwvdGl0bGU+PGcgaWQ9IkxheWVyXzIiPjxnIGlkPSJMYXllcl8zIj48cGF0aCBjbGFzcz0iY2xzLTEiIGQ9Ik01MS44NywwQzIzLjcxLDAsMCwyMi44MywwLDUxYzAsLjkxLDAsNTIuODEsMCw1Mi44MWw1MS44Ni0uMDVjMjguMTYsMCw1MS0yMy43MSw1MS01MS44N1M4MCwwLDUxLjg3LDBaIi8+PHBhdGggY2xhc3M9ImNscy0yIiBkPSJNNTIuMzcsMTkuNzRBMzEuNjIsMzEuNjIsMCwwLDAsMjQuNTgsNjYuNDFsLTUuNzIsMTguNEwzOS40LDgwLjE3YTMxLjYxLDMxLjYxLDAsMSwwLDEzLTYwLjQzWiIvPjxwYXRoIGNsYXNzPSJjbHMtMyIgZD0iTTc3LjQ1LDMyLjEyYTMxLjYsMzEuNiwwLDAsMS0zOC4wNSw0OEwxOC44Niw4NC44MmwyMC45MS0yLjQ3QTMxLjYsMzEuNiwwLDAsMCw3Ny40NSwzMi4xMloiLz48cGF0aCBjbGFzcz0iY2xzLTQiIGQ9Ik03MS42MywyNi4yOUEzMS42LDMxLjYsMCwwLDEsMzguOCw3OEwxOC44Niw4NC44MiwzOS40LDgwLjE3QTMxLjYsMzEuNiwwLDAsMCw3MS42MywyNi4yOVoiLz48cGF0aCBjbGFzcz0iY2xzLTUiIGQ9Ik0yNi40Nyw2Ny4xMWEzMS42MSwzMS42MSwwLDAsMSw1MS0zNUEzMS42MSwzMS42MSwwLDAsMCwyNC41OCw2Ni40MWwtNS43MiwxOC40WiIvPjxwYXRoIGNsYXNzPSJjbHMtNiIgZD0iTTI0LjU4LDY2LjQxQTMxLjYxLDMxLjYxLDAsMCwxLDcxLjYzLDI2LjI5YTMxLjYxLDMxLjYxLDAsMCwwLTQ5LDM5LjYzbC0zLjc2LDE4LjlaIi8+PC9nPjwvZz48L3N2Zz4="
			/>
		</a>
	</svelte:fragment>
</DocNotebookDropdown>

<script lang="ts">
	import { onMount } from "svelte";

	import Dropdown from "./Dropdown.svelte";
	import DropdownEntry from "./DropdownEntry.svelte";

	export let options: { label: string; value: string }[] = [];
	export let classNames = "";
	let dropdownEl: HTMLDivElement;

	const googleColabOptions = options.filter((o) => o.value.includes("colab.research.google.com"));
	const awsStudioOptions = options.filter((o) => o.value.includes("studiolab.sagemaker.aws"));

	function onClick(url: string) {
		window.open(url);
	}

	function onResize() {
		// avoid DocNotebookDropdown overlapping with doc titles (i.e. h1 elements) on smaller screens because of absolute positioning
		const h1El = document.querySelector(".prose-doc h1");
		const h1SpanEl = document.querySelector(".prose-doc h1 > span");
		if (h1El && h1SpanEl) {
			const { width: h1Widht } = h1El.getBoundingClientRect();
			const { width: spanWidth } = h1SpanEl.getBoundingClientRect();
			// correct calculation of dropdownEl's width; othwrwise, the width can count in negative (empty) spaces
			let dropdownWidth = 0;
			for (let i = 0; i < dropdownEl.children.length; i++) {
				dropdownWidth += dropdownEl.children.item(i).clientWidth;
			}
			const bufferMargin = 20;
			if (h1Widht - spanWidth < dropdownWidth + bufferMargin) {
				dropdownEl.classList.remove("absolute");
			} else {
				dropdownEl.classList.add("absolute");
			}
		}
	}

	onMount(() => {
		onResize();
	});
</script>

<svelte:window on:resize={onResize} />

<div class="flex space-x-1 {classNames}" bind:this={dropdownEl}>
	<Dropdown btnLabel="" classNames="colab-dropdown" noBtnClass useDeprecatedJS={false}>
		<slot slot="button">
			<img
				alt="Open In Colab"
				class="!m-0"
				src="https://colab.research.google.com/assets/colab-badge.svg"
			/>
		</slot>
		<slot slot="menu">
			{#each googleColabOptions as { label, value }}
				<DropdownEntry
					classNames="text-sm !no-underline"
					iconClassNames="text-gray-500"
					{label}
					onClick={() => onClick(value)}
					useDeprecatedJS={false}
				/>
			{/each}
		</slot>
	</Dropdown>
	<Dropdown btnLabel="" classNames="colab-dropdown" noBtnClass useDeprecatedJS={false}>
		<slot slot="button">
			<img
				alt="Open In Studio Lab"
				class="!m-0"
				src="https://studiolab.sagemaker.aws/studiolab.svg"
			/>
		</slot>
		<slot slot="menu">
			{#each awsStudioOptions as { label, value }}
				<DropdownEntry
					classNames="text-sm !no-underline"
					iconClassNames="text-gray-500"
					{label}
					onClick={() => onClick(value)}
					useDeprecatedJS={false}
				/>
			{/each}
		</slot>
	</Dropdown>
</div>

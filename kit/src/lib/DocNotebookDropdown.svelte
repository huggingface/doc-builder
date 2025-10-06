<script lang="ts">
	import Dropdown from "./Dropdown.svelte";
	import DropdownEntry from "./DropdownEntry.svelte";

	export let options: { label: string; value: string }[] = [];
	export let classNames = "";
	export let containerStyle = "";

	const googleColabOptions = options.filter((o) => o.value.includes("colab.research.google.com"));
	const awsStudioOptions = options.filter((o) => o.value.includes("studiolab.sagemaker.aws"));

	function onClick(url: string) {
		window.open(url);
	}
</script>

<div class="flex space-x-1 {classNames}" style={containerStyle}>
	<slot name="alwaysVisible" />
	{#if googleColabOptions.length === 1}
		<a href={googleColabOptions[0].value} target="_blank">
			<img
				alt="Open In Colab"
				class="!m-0"
				src="https://colab.research.google.com/assets/colab-badge.svg"
			/>
		</a>
	{:else if googleColabOptions.length > 1}
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
	{/if}
	{#if awsStudioOptions.length === 1}
		<a href={awsStudioOptions[0].value} target="_blank">
			<img
				alt="Open In Studio Lab"
				class="!m-0"
				src="https://studiolab.sagemaker.aws/studiolab.svg"
			/>
		</a>
	{:else if awsStudioOptions.length > 1}
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
	{/if}
</div>

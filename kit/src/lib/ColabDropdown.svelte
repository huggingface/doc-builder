<script lang="ts">
	import Dropdown from "./Dropdown.svelte";
	import DropdownEntry from "./DropdownEntry.svelte";

	interface Props {
		options?: { label: string; value: string }[];
		classNames?: string;
		children?: import("svelte").Snippet;
	}

	let { options = [], classNames = "", children }: Props = $props();

	function onClick(url: string) {
		window.open(url);
	}
</script>

<div class={classNames}>
	<Dropdown btnLabel="" classNames="colab-dropdown" noBtnClass useDeprecatedJS={false}>
		{#snippet button()}
			{#if children}{@render children()}{:else}
				<img
					alt="Open In Colab"
					class="!m-0"
					src="https://colab.research.google.com/assets/colab-badge.svg"
				/>
			{/if}
		{/snippet}
		{#snippet menu()}
			{#if children}{@render children()}{:else}
				{#each options as { label, value }}
					<DropdownEntry
						classNames="text-sm !no-underline"
						iconClassNames="text-gray-500"
						{label}
						onClick={() => onClick(value)}
						useDeprecatedJS={false}
					/>
				{/each}
			{/if}
		{/snippet}
	</Dropdown>
</div>

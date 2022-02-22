<script lang="ts">
	import Dropdown from "./Dropdown.svelte";
	import DropdownEntry from "./DropdownEntry.svelte";

	export let options: { label: string; value: string }[] = [];
	export let classNames = "";

	function onClick(url: string) {
		window.open(url);
	}
</script>

<div class={classNames}>
	<Dropdown btnLabel="" classNames="colab-dropdown" noBtnClass useDeprecatedJS={false}>
		<slot slot="button">
			<img
				alt="Open In Colab"
				class="!m-0"
				src="https://colab.research.google.com/assets/colab-badge.svg"
			/>
		</slot>
		<slot slot="menu">
			{#each options as { label, value }}
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

<script lang="ts">
	import type { Group } from "./types";
	import { group } from "./stores";
	import IconPytorch from "./IconPytorch.svelte";
	import IconTensorflow from "./IconTensorflow.svelte";

	export let ids: string[];

	const GROUPS = [
		{
			id: "pt",
			classNames: "bg-red-50 text-red-600",
			icon: IconPytorch,
			name: "Pytorch",
			group: "group1",
		},
		{
			id: "tf",
			classNames: "bg-orange-50 text-yellow-600",
			icon: IconTensorflow,
			name: "TensorFlow",
			group: "group2",
		},
		{
			id: "stringapi",
			name: "String API",
			group: "group1",
		},
		{
			id: "readinstruction",
			name: "ReadInstruction",
			group: "group2",
		},
	];

	function changeGroup(_group: string) {
		$group = _group as Group;
	}
</script>

<div>
	<div
		class="bg-white leading-none border border-gray-100 rounded-lg inline-flex p-0.5 text-sm mb-4 select-none"
	>
		{#each GROUPS.filter((g) => ids.includes(g.id)) as g, i}
			<button
				class="flex justify-center py-1.5 px-2.5 focus:outline-none
			rounded-{i ? 'r' : 'l'}
			{g.group !== $group && 'text-gray-500 filter grayscale'}"
				on:click={() => changeGroup(g.group)}
			>
				{#if g.icon}
					<svelte:component this={g.icon} classNames="mr-1.5" />
				{/if}
				<p style="margin: 0px;">
					{g.name}
				</p>
			</button>
		{/each}
	</div>
</div>

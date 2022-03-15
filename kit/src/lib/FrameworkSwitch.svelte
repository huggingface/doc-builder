<script lang="ts">
	import type { Group } from "./types";
	import { getGroupStore } from "./stores";
	import IconPytorch from "./IconPytorch.svelte";
	import IconTensorflow from "./IconTensorflow.svelte";

	export let ids: string[];
	const storeKey = ids.join("-");
	const group = getGroupStore(storeKey);

	const GROUPS = [
		{
			id: "pt",
			classNames: "",
			icon: IconPytorch,
			name: "Pytorch",
			group: "group1"
		},
		{
			id: "tf",
			classNames: "",
			icon: IconTensorflow,
			name: "TensorFlow",
			group: "group2"
		},
		{
			id: "stringapi",
			classNames: "text-blue-600",
			name: "String API",
			group: "group1"
		},
		{
			id: "readinstruction",
			classNames: "text-blue-600",
			name: "ReadInstruction",
			group: "group2"
		}
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
				<p class="!m-0 {g.classNames}">
					{g.name}
				</p>
			</button>
		{/each}
	</div>
</div>

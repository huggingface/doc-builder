<script lang="ts">
	import type { Framework } from "./types";
	import { fw } from "./stores";
	import IconPytorch from "./IconPytorch.svelte";
	import IconTensorflow from "./IconTensorflow.svelte";

	const FRAMEWORKS = [
		{
			id: "pt",
			classNames: "bg-red-50 text-red-600",
			icon: IconPytorch,
			name: "Pytorch"
		},
		{
			id: "tf",
			classNames: "bg-orange-50 text-yellow-600",
			icon: IconTensorflow,
			name: "TensorFlow"
		}
	] as const;

	function changeFw(_fw: Framework) {
		$fw = _fw;
	}
</script>

<div
	class="bg-white leading-none border border-gray-100 rounded-lg flex p-0.5 w-56 text-sm mb-4 select-none"
>
	{#each FRAMEWORKS as { icon, id, name }, i}
		<button
			class="flex justify-center flex-1 py-1.5 px-2.5 focus:outline-none
			rounded-{i ? 'r' : 'l'}
			{id !== $fw && 'text-gray-500 filter grayscale'}"
			on:click={() => changeFw(id)}
		>
			<svelte:component this={icon} classNames="mr-1.5" />
			<p style="margin: 0px;">
				{name}
			</p>
		</button>
	{/each}
</div>

<script lang="ts">
	import type { CourseFramework } from "./types";

	import IconPytorch from "./IconPytorch.svelte";
	import IconTensorflow from "./IconTensorflow.svelte";

	export let fw: CourseFramework;

	const FRAMEWORKS = [
		{
			id: "pt",
			classNames: "bg-red-50 dark:bg-transparent text-red-600",
			icon: IconPytorch,
			name: "Pytorch",
		},
		{
			id: "tf",
			classNames: "bg-orange-50 dark:bg-transparent text-yellow-600",
			icon: IconTensorflow,
			name: "TensorFlow",
		},
	] as const;
</script>

<div class="bg-white leading-none border border-gray-100 rounded-lg flex p-0.5 w-56 text-sm mb-4">
	{#each FRAMEWORKS as f, i}
		<a
			class="flex justify-center flex-1 py-1.5 px-2.5 focus:outline-none !no-underline
                rounded-{i ? 'r' : 'l'} 
                {f.id === fw ? f.classNames : 'text-gray-500 filter grayscale'}"
			href="?fw={f.id}"
		>
			<svelte:component this={f.icon} classNames="mr-1.5" />
			{f.name}
		</a>
	{/each}
</div>

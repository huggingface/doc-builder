<script lang="ts">
	import type { SvelteComponent } from "svelte";
	import type { Framework } from "./types";

	import { onMount } from "svelte";
	import { getFrameworkStore } from "./stores";
	import IconPytorch from "./IconPytorch.svelte";
	import IconTensorflow from "./IconTensorflow.svelte";
	import IconJax from "./IconJax.svelte";
	import IconEyeShow from "./IconEyeShow.svelte";
	import IconEyeHide from "./IconEyeHide.svelte";

	export let framework: Framework;

	let containerEl: HTMLDivElement;

	const FRAMEWORK_CONFIG: Record<Framework, { Icon: typeof SvelteComponent; label: string }> = {
		pytorch: {
			Icon: IconPytorch,
			label: "Pytorch"
		},
		tensorflow: {
			Icon: IconTensorflow,
			label: "TensorFlow"
		},
		jax: {
			Icon: IconJax,
			label: "JAX"
		}
	};
	const { Icon, label } = FRAMEWORK_CONFIG[framework];
	const localStorageKey = `hf_doc_framework_${framework}_is_hidden`;
	const frameworkStore = getFrameworkStore(framework);

	function toggleHidden() {
		$frameworkStore = !$frameworkStore;
		localStorage.setItem(localStorageKey, $frameworkStore ? "true" : "false");
	}

	onMount(() => {
		const hashLink = window.location.hash.slice(1);
		const headerClass = "header-link";
		const headings = containerEl.querySelectorAll(`.${headerClass}`);
		const hashLinks = new Set([...headings].map((h) => h.id));

		if(hashLinks.has(hashLink)){
			$frameworkStore = false;
		}else if (localStorage.getItem(localStorageKey) === "true") {
			$frameworkStore = true;
		}
	});
</script>

<div class="border border-gray-200 rounded-xl px-4 relative"
	bind:this={containerEl}
>
	<div class="flex h-[22px] -mt-[12.5px] px-2.5 justify-between leading-none">
		<div class="px-2.5 flex items-center space-x-1 bg-white dark:bg-gray-950">
			<svelte:component this={Icon} />
			<span>{label}</span>
		</div>
		{#if !$frameworkStore}
			<div
				class="cursor-pointer flex items-center justify-center space-x-1 text-sm px-2.5 bg-white dark:bg-gray-950 hover:underline "
				on:click={toggleHidden}
			>
				<IconEyeHide />
				<span>Hide {label} content</span>
			</div>
		{/if}
	</div>
	{#if $frameworkStore}
		<div
			class="cursor-pointer flex -mt-[12.5px] items-center justify-center space-x-1 py-2.5 text-sm hover:underline"
			on:click={toggleHidden}
		>
			<IconEyeShow />
			<span>Show {label} content</span>
		</div>
	{:else}
		<slot />
	{/if}
</div>

<script lang="ts">
	import type { SvelteComponent } from "svelte";
	import type { Framework } from "./types";

	import { onMount } from "svelte";
	import { getFrameworkStore, FrameworkState } from "./stores";
	import IconPytorch from "./IconPytorch.svelte";
	import IconTensorflow from "./IconTensorflow.svelte";
	import IconJax from "./IconJax.svelte";
	import IconEyeShow from "./IconEyeShow.svelte";
	import IconEyeHide from "./IconEyeHide.svelte";

	export let framework: Framework;

	let containerEl: HTMLDivElement;
	let hashLinks = new Set();

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
	const fwStore = getFrameworkStore(framework);

	$: isClosed = $fwStore === FrameworkState.CLOSED;

	function toggleHidden() {
		$fwStore = $fwStore !== FrameworkState.CLOSED ? FrameworkState.CLOSED : FrameworkState.OPEN;
		localStorage.setItem(localStorageKey, $fwStore);
	}

	function onHashChange() {
		const hashLink = window.location.hash.slice(1);
		if (hashLinks.has(hashLink)) {
			$fwStore = FrameworkState.HASHASHLINK;
			localStorage.setItem(localStorageKey, $fwStore);
		}
	}

	onMount(() => {
		const hashLink = window.location.hash.slice(1);
		const headerClass = "header-link";
		const headings = containerEl.querySelectorAll(`.${headerClass}`);
		hashLinks = new Set([...headings].map((h) => h.id));
		const localState = localStorage.getItem(localStorageKey);

		if (hashLinks.has(hashLink)) {
			$fwStore = FrameworkState.HASHASHLINK;
		} else if (localState === FrameworkState.CLOSED && $fwStore !== FrameworkState.HASHASHLINK) {
			$fwStore = FrameworkState.CLOSED;
		}
	});
</script>

<svelte:window on:hashchange={onHashChange} />

<div class="border border-gray-200 rounded-xl px-4 relative" bind:this={containerEl}>
	<div class="flex h-[22px] mt-[-12.5px] justify-between leading-none" >
		<div class="flex px-1 items-center space-x-1 bg-white dark:bg-gray-950">
			<svelte:component this={Icon} />
			<span>{label}</span>
		</div>
		{#if !isClosed}
			<div
				class="cursor-pointer flex items-center justify-center space-x-1 text-sm px-2 bg-white dark:bg-gray-950 hover:underline leading-none"
				on:click={toggleHidden}
			>
				<IconEyeHide size={"0.9em"} />
				<span>Hide {label} content</span>
			</div>
		{/if}
	</div>
	{#if isClosed}
		<div
			class="cursor-pointer mt-[-12.5px] flex items-center justify-center space-x-1 py-4 text-sm hover:underline leading-none"
			on:click={toggleHidden}
		>
			<IconEyeShow size={"0.9em"} />
			<span>Show {label} content</span>
		</div>
	{:else}
		<div class="framework-content">
			<slot />
		</div>
	{/if}
</div>

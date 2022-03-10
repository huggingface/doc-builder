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

	$: isClosed = $fwStore.isClosed && !$fwStore.hasHashLink;

	function toggleHidden() {
		$fwStore.isClosed = !$fwStore.isClosed;
		if ($fwStore.isClosed) {
			$fwStore.hasHashLink = false;
		}
		localStorage.setItem(localStorageKey, $fwStore.isClosed ? "true" : "false");
	}

	function onHashChange() {
		const hashLink = window.location.hash.slice(1);
		if (hashLinks.has(hashLink)) {
			$fwStore.hasHashLink = true;
		}
	}

	onMount(() => {
		const hashLink = window.location.hash.slice(1);
		const headerClass = "header-link";
		const headings = containerEl.querySelectorAll(`.${headerClass}`);
		hashLinks = new Set([...headings].map((h) => h.id));

		if (hashLinks.has(hashLink)) {
			$fwStore.isClosed = false;
			$fwStore.hasHashLink = true;
		} else if (localStorage.getItem(localStorageKey) === "true") {
			$fwStore.isClosed = true;
		}
	});
</script>

<svelte:window on:hashchange={onHashChange} />

<div class="border border-gray-200 rounded-xl px-4 relative" bind:this={containerEl}>
	<div class="flex h-[22px] px-2.5 justify-between leading-none" style="margin-top: -12.5px;">
		<div class="px-2.5 flex items-center space-x-1 bg-white dark:bg-gray-950">
			<svelte:component this={Icon} />
			<span>{label}</span>
		</div>
		{#if !isClosed}
			<div
				class="cursor-pointer flex items-center justify-center space-x-1 text-sm px-2.5 bg-white dark:bg-gray-950 hover:underline"
				on:click={toggleHidden}
			>
				<IconEyeHide />
				<span>Hide {label} content</span>
			</div>
		{/if}
	</div>
	{#if isClosed}
		<div
			class="cursor-pointer flex items-center justify-center space-x-1 py-2.5 text-sm hover:underline"
			style="margin-top: -12.5px;"
			on:click={toggleHidden}
		>
			<IconEyeShow />
			<span>Show {label} content</span>
		</div>
	{:else}
		<slot />
	{/if}
</div>

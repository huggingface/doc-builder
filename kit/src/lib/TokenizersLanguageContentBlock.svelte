<script lang="ts">
	import type { SvelteComponent } from "svelte";
	import type { TokenizersLanguage } from "./types";

	import { onMount } from "svelte";
	import { getTokenizersLangState, AccordianState } from "./stores";
	import IconPython from "./IconPython.svelte";
	import IconRust from "./IconRust.svelte";
	import IconNode from "./IconNode.svelte";
	import IconEyeShow from "./IconEyeShow.svelte";
	import IconEyeHide from "./IconEyeHide.svelte";

	export let language: TokenizersLanguage;

	let containerEl: HTMLDivElement;
	let hashLinks = new Set();

	const TOKENIZERS_LANGUAGE_CONFIG: Record<
		TokenizersLanguage,
		{ Icon: typeof SvelteComponent; label: string }
	> = {
		python: {
			Icon: IconPython,
			label: "Python"
		},
		rust: {
			Icon: IconRust,
			label: "Rust"
		},
		node: {
			Icon: IconNode,
			label: "Node"
		}
	};
	const { Icon, label } = TOKENIZERS_LANGUAGE_CONFIG[language];
	const localStorageKey = `hf_doc_tokenizer_lang_${language}_is_hidden`;
	const langStore = getTokenizersLangState(language);

	$: isClosed = $langStore === AccordianState.CLOSED;

	function toggleHidden() {
		$langStore = $langStore !== AccordianState.CLOSED ? AccordianState.CLOSED : AccordianState.OPEN;
		localStorage.setItem(localStorageKey, $langStore);
	}

	function onHashChange() {
		const hashLink = window.location.hash.slice(1);
		if (hashLinks.has(hashLink)) {
			$langStore = AccordianState.HASHASHLINK;
			localStorage.setItem(localStorageKey, $langStore);
		}
	}

	onMount(() => {
		const hashLink = window.location.hash.slice(1);
		const headerClass = "header-link";
		const headings = containerEl.querySelectorAll(`.${headerClass}`);
		hashLinks = new Set([...headings].map((h) => h.id));
		const localState = localStorage.getItem(localStorageKey);

		if (hashLinks.has(hashLink)) {
			$langStore = AccordianState.HASHASHLINK;
		} else if (localState === AccordianState.CLOSED && $langStore !== AccordianState.HASHASHLINK) {
			$langStore = AccordianState.CLOSED;
		}
	});
</script>

<svelte:window on:hashchange={onHashChange} />

<div class="border border-gray-200 rounded-xl px-4 relative" bind:this={containerEl}>
	<div class="flex h-[22px] mt-[-12.5px] justify-between leading-none">
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
		<div class="language-content">
			<slot />
		</div>
	{/if}
</div>

<script lang="ts">
	import type { Component } from "svelte";
	import DropdownMenu from "./DropdownMenu.svelte";
	import IconCaretDown from "./IconCaretDown.svelte";

	interface Props {
		classNames?: string;
		btnClassNames?: string;
		btnIcon?: Component<{ classNames?: string }> | undefined;
		btnIconClassNames?: string;
		btnLabel?: string;
		forceMenuAlignement?: "left" | "right" | undefined;
		menuClassNames?: string;
		noBtnClass?: boolean | undefined;
		selectedValue?: string | undefined;
		useDeprecatedJS?: boolean;
		withBtnCaret?: boolean;
		button?: import("svelte").Snippet;
		menu?: import("svelte").Snippet;
	}

	let {
		classNames = "",
		btnClassNames = "",
		btnIcon = undefined,
		btnIconClassNames = "",
		btnLabel = "",
		forceMenuAlignement = undefined,
		menuClassNames = "",
		noBtnClass = undefined,
		selectedValue = undefined,
		useDeprecatedJS = true,
		withBtnCaret = false,
		button,
		menu,
	}: Props = $props();

	let element: HTMLElement | undefined = $state(undefined);
	let isOpen = $state(false);

	function onClose(e: Event) {
		if (e.target) {
			if ((e.target as HTMLElement | undefined)?.className.includes("do-not-close-dropdown")) {
				return;
			}
		}
		isOpen = false;
	}
</script>

<div class="relative {classNames} {useDeprecatedJS ? 'v2-dropdown' : ''}" bind:this={element}>
	<!-- Button -->
	<button
		class="
			{btnClassNames}
			{!noBtnClass ? 'cursor-pointer w-full btn text-sm' : ''}
			{useDeprecatedJS ? 'v2-dropdown-button' : ''}"
		onclick={() => (isOpen = !isOpen)}
		type="button"
	>
		<!-- The "button" slot can overwrite the defaut button content -->
		{#if button}
			{@render button?.()}
		{:else}
			{#if btnIcon}
				{@const SvelteComponent_1 = btnIcon}
				<SvelteComponent_1 classNames="mr-1.5 {btnIconClassNames}" />
			{/if}
			{btnLabel}
			{#if withBtnCaret}
				<IconCaretDown classNames="-mr-1 text-gray-500" />
			{/if}
		{/if}
	</button>
	<!-- /Button -->
	<!-- Menu -->
	{#if isOpen || useDeprecatedJS}
		<DropdownMenu
			classNames="{menuClassNames} {useDeprecatedJS ? 'v2-dropdown-menu hidden' : ''}"
			dropdownElement={element}
			forceAlignement={forceMenuAlignement}
			{onClose}
		>
			{@render menu?.()}
		</DropdownMenu>
	{/if}
	<!-- Menu -->
</div>

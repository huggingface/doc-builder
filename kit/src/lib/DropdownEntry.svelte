<script lang="ts">
	import type { Component } from "svelte";

	interface Props {
		classNames?: string;
		dataLabel?: string | undefined;
		dataUrl?: string | undefined;
		dataValue?: string | undefined;
		href?: string | undefined;
		icon?: Component<{ classNames?: string }> | undefined;
		iconClassNames?: string;
		label?: string;
		noFollow?: boolean;
		underline?: boolean;
		onClick?: (e: MouseEvent) => void;
		targetBlank?: boolean;
		useDeprecatedJS?: boolean;
		children?: import("svelte").Snippet;
	}

	let {
		classNames = "",
		dataLabel = undefined,
		dataUrl = undefined,
		dataValue = undefined,
		href = undefined,
		icon = undefined,
		iconClassNames = "",
		label = "",
		noFollow = false,
		underline = false,
		onClick = () => {},
		targetBlank = false,
		useDeprecatedJS = true,
		children,
	}: Props = $props();
</script>

<li class="not-prose">
	<a
		class="flex items-center hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer px-3 py-1.5 whitespace-nowrap
			{classNames}
			{underline ? 'hover:underline' : ''}
			{useDeprecatedJS ? 'v2-dropdown-entry' : ''}"
		data-label={dataLabel}
		data-url={dataUrl}
		data-value={dataValue}
		{href}
		onclick={onClick}
		rel={noFollow ? "nofollow" : undefined}
		target={targetBlank ? "_blank" : undefined}
	>
		<!-- Adding children to the DropdownEntry element overwrite the default label/icon stuff -->
		{#if children}
			{@render children?.()}
		{:else}
			{#if icon}
				{@const SvelteComponent_1 = icon}
				<SvelteComponent_1 classNames="mr-1.5 {iconClassNames}" />
			{/if}
			{label}
		{/if}
	</a>
</li>

<script lang="ts">
	import { onMount } from "svelte";
	import IconAgent from "./IconAgent.svelte";
	import IconCaret from "./IconCaret.svelte";
	import IconCopy from "./IconCopy.svelte";
	import { copyToClipboard } from "./copyToClipboard";

	interface Props {
		// the prompt's markdown, base64-encoded by the mdsvex preprocessor
		source?: string;
		children?: import("svelte").Snippet;
	}

	// matches `max-h-32` below
	const COLLAPSED_HEIGHT = 128;

	let { source = "", children }: Props = $props();
	let content: HTMLDivElement;
	let expanded = $state(false);
	let overflowing = $state(false);
	let copied = $state(false);
	let timeout: ReturnType<typeof setTimeout>;

	let collapsed = $derived(!expanded && overflowing);

	onMount(() => {
		const observer = new ResizeObserver(() => {
			overflowing = content.scrollHeight > COLLAPSED_HEIGHT;
		});
		observer.observe(content);
		return () => {
			observer.disconnect();
			clearTimeout(timeout);
		};
	});

	function copy() {
		// a hand-written <AgentPrompt> tag has no source: copy its rendered text
		copyToClipboard(source ? decodeURIComponent(atob(source)) : content.innerText.trim());
		copied = true;
		clearTimeout(timeout);
		timeout = setTimeout(() => (copied = false), 1500);
	}
</script>

<!-- tailwind classes only: kit's CSS is emptied in production builds and the hub's CSS styles the docs, so
	every class used here must exist in moon-landing's build (see its DocPage/TailwindWhitelist.svelte) -->
<div class="my-6 overflow-hidden rounded-xl border border-gray-200 dark:border-gray-850">
	<div
		class="flex items-center justify-between gap-2 border-b border-gray-200 bg-linear-to-t from-gray-100-to-white px-3 py-1.5 dark:border-gray-850"
	>
		<span class="flex items-center gap-1.5 text-sm font-semibold text-gray-800 dark:text-gray-200">
			<IconAgent classNames="text-blue-500" />
			Agent prompt
		</span>
		<button
			type="button"
			onclick={copy}
			title="Copy agent prompt"
			aria-live="polite"
			class="inline-flex items-center gap-1 h-7 px-2 text-sm font-medium text-gray-800 border rounded-md border-gray-200 bg-white hover:shadow-inner dark:border-gray-850 dark:bg-gray-950 dark:text-gray-200 dark:hover:bg-gray-800"
		>
			<IconCopy classNames="size-3.5" />
			{copied ? "Copied" : "Copy"}
		</button>
	</div>
	<div class="relative">
		<div
			class="prose max-w-none px-4 py-3 {collapsed ? 'max-h-32 overflow-hidden' : ''}"
			bind:this={content}
		>
			{@render children?.()}
		</div>
		{#if collapsed}
			<div
				class="pointer-events-none absolute inset-x-0 bottom-0 h-12 bg-linear-to-t from-white dark:from-gray-950"
			></div>
		{/if}
	</div>
	{#if overflowing}
		<div class="flex justify-center pb-3">
			<button
				type="button"
				onclick={() => (expanded = !expanded)}
				aria-expanded={expanded}
				class="flex h-7 items-center rounded-lg border border-gray-100 px-2.5 text-sm font-medium text-gray-800 hover:bg-gray-100 hover:text-gray-900 dark:hover:bg-gray-800 dark:hover:text-gray-200"
			>
				<IconCaret
					classNames="mr-1.5 text-xs text-gray-400 transition-transform {expanded
						? 'rotate-180'
						: 'rotate-0'}"
				/>
				{expanded ? "Show less" : "Show more"}
			</button>
		</div>
	{/if}
</div>

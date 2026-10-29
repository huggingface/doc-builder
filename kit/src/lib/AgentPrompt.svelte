<script lang="ts">
	import { onMount } from "svelte";
	import IconCaretDown from "./IconCaretDown.svelte";
	import { copyToClipboard } from "./copyToClipboard";

	interface Props {
		children?: import("svelte").Snippet;
	}

	let { children }: Props = $props();
	let content: HTMLDivElement;
	let expanded = $state(false);
	let overflowing = $state(false);
	let copied = $state(false);
	let timeout: ReturnType<typeof setTimeout>;

	onMount(() => {
		const observer = new ResizeObserver(() => {
			overflowing = content.scrollHeight > 96;
		});
		observer.observe(content);
		return () => {
			observer.disconnect();
			clearTimeout(timeout);
		};
	});

	function copy() {
		copyToClipboard(content.innerText.trim());
		copied = true;
		clearTimeout(timeout);
		timeout = setTimeout(() => (copied = false), 1500);
	}
</script>

<div class="agent-prompt">
	<div class="agent-prompt-header">
		<span>Agent prompt</span>
		<div class="agent-prompt-actions">
			<button type="button" onclick={copy} aria-label="Copy agent prompt" title="Copy agent prompt">
				<svg
					width="16"
					height="16"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
					stroke-linecap="round"
					stroke-linejoin="round"
					aria-hidden="true"
				>
					<rect width="14" height="14" x="8" y="8" rx="2" ry="2" />
					<path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
				</svg>
			</button>
		</div>
	</div>
	<div class:collapsed={!expanded && overflowing} class="agent-prompt-body" bind:this={content}>
		{@render children?.()}
	</div>
	{#if overflowing}
		<button
			class="agent-prompt-more"
			type="button"
			onclick={() => (expanded = !expanded)}
			aria-expanded={expanded}
		>
			{expanded ? "Show less" : "Show more"}
			<IconCaretDown classNames={expanded ? "rotate-180" : ""} />
		</button>
	{/if}
	<span class="sr-only" aria-live="polite">{copied ? "Prompt copied" : ""}</span>
</div>

<style>
	.agent-prompt {
		position: relative;
		margin: 1.5rem 0 2rem;
		border: 1px solid #d1d5db;
		border-radius: 0.75rem;
	}
	.agent-prompt-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.75rem 1rem;
		border-bottom: 1px solid #d1d5db;
		font-weight: 600;
		background: #f9fafb;
		border-radius: 0.75rem 0.75rem 0 0;
	}
	.agent-prompt-actions {
		display: flex;
		gap: 0.75rem;
	}
	.agent-prompt-actions button {
		display: flex;
		padding: 0.25rem;
		cursor: pointer;
	}
	.agent-prompt-body {
		padding: 1rem;
		overflow: hidden;
	}
	.agent-prompt-body.collapsed {
		max-height: 96px;
		mask-image: linear-gradient(black 55%, transparent);
	}
	.agent-prompt-body :global(p:first-child) {
		margin-top: 0;
	}
	.agent-prompt-body :global(p:last-child) {
		margin-bottom: 0;
	}
	.agent-prompt-more {
		display: flex;
		align-items: center;
		gap: 0.25rem;
		margin: 0.25rem auto 0.75rem;
		padding: 0.25rem;
		font-size: 0.875rem;
		font-weight: 600;
		cursor: pointer;
		white-space: nowrap;
	}
	:global(.dark) .agent-prompt,
	:global(.dark) .agent-prompt-header,
	:global(.dark) .agent-prompt-more {
		border-color: #4b5563;
	}
	:global(.dark) .agent-prompt-header {
		background: #1f2937;
	}
</style>

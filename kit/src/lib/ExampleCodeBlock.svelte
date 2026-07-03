<script lang="ts">
	import { onMount } from "svelte";

	import IconCopyLink from "./IconCopyLink.svelte";

	interface Props {
		anchor: string;
		children?: import("svelte").Snippet;
	}

	let { anchor, children }: Props = $props();

	const bgHighlightClass = "bg-yellow-50 dark:bg-[#494a3d]";
	let containerEl = $state<HTMLElement>()!;

	function onHashChange() {
		const { hash } = window.location;
		const hashlink = hash.substring(1);

		if (containerEl) {
			containerEl.classList.remove(...bgHighlightClass.split(" "));
		}
		if (hashlink === anchor) {
			containerEl.classList.add(...bgHighlightClass.split(" "));
		}
	}

	onMount(() => {
		onHashChange();
	});
</script>

<svelte:window onhashchange={onHashChange} />

<div class="relative group rounded-md" bind:this={containerEl}>
	<a
		id={anchor}
		class="header-link block pr-0.5 text-lg no-hover:hidden with-hover:absolute with-hover:p-1.5 with-hover:opacity-0 with-hover:group-hover:opacity-100 with-hover:right-full"
		href={`#${anchor}`}
	>
		<span><IconCopyLink classNames="text-smd" /></span>
	</a>
	{@render children?.()}
</div>

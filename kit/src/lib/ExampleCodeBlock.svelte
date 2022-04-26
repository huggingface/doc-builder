<script lang="ts">
	import { onMount } from "svelte";

	import IconCopyLink from "./IconCopyLink.svelte";

	export let anchor: string;

	const bgHighlightClass = "bg-yellow-50 dark:bg-[#494a3d]";
	let containerEl: HTMLElement;

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

<svelte:window on:hashchange={onHashChange} />

<div class="relative group rounded-md" bind:this={containerEl}>
	<a
		id={anchor}
		class="header-link block pr-0.5 text-lg no-hover:hidden with-hover:absolute with-hover:p-1.5 with-hover:opacity-0 with-hover:group-hover:opacity-100 with-hover:right-full"
		href={`#${anchor}`}
	>
		<span><IconCopyLink classNames="text-smd" /></span>
	</a>
	<slot />
</div>

<script lang="ts">
	import { onMount } from "svelte";

	type Alignement = "left" | "right";

	interface Props {
		classNames?: string;
		dropdownElement?: HTMLElement | undefined;
		forceAlignement?: Alignement | undefined;
		onClose: (e: MouseEvent) => void;
		children?: import("svelte").Snippet;
	}

	let {
		classNames = "",
		dropdownElement = undefined,
		forceAlignement = undefined,
		onClose,
		children,
	}: Props = $props();

	// MUST be set to left if forceAlignement is undefined or else
	// the browser won't be able to properly compute x and width
	let alignement: Alignement = $state(forceAlignement ?? "left");
	let element: HTMLElement | undefined = $state();

	onMount(() => {
		document.addEventListener("click", handleClickDocument);

		if (!forceAlignement) {
			const docWidth = document.documentElement.clientWidth;
			const domRect = element?.getBoundingClientRect();
			const left = domRect?.["left"] ?? 0;
			const width = domRect?.["width"] ?? 0;
			alignement = left + width > docWidth ? "right" : "left";
		}

		return () => {
			document.removeEventListener("click", handleClickDocument);
		};
	});

	function handleClickDocument(e: MouseEvent) {
		// We ignore clicks that happens inside the Dropdown itself
		// (prevent race condition  with other click handlers)
		const targetElement = e.target as HTMLElement;
		if (targetElement !== dropdownElement && !dropdownElement?.contains(targetElement)) {
			onClose(e);
		}
	}
</script>

<div
	bind:this={element}
	class="absolute top-full mt-1 min-w-full w-auto bg-white rounded-xl overflow-hidden shadow-lg z-10 border border-gray-100
		{alignement === 'right' ? 'right-0' : 'left-0'}
		{classNames}"
	onclick={onClose}
>
	<ul class="min-w-full w-auto">
		{@render children?.()}
	</ul>
</div>

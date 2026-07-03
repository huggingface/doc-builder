<script lang="ts">
	interface Props {
		txt: string;
		x: number;
		y: number;
		id: string;
	}

	let { txt, x, y, id }: Props = $props();
</script>

{#if txt}
	<div
		class="absolute text-base py-1.5 p-2 break-words bg-white border-2 border-black dark:border-gray-500 rounded shadow-alternate-xl z-50 {txt.length >
		1000
			? 'max-w-lg'
			: 'max-w-xs'}"
		style="
			top: {y + 15}px;
			left: {x + 15}px;"
		{id}
	>
		{@html txt}
	</div>
{/if}

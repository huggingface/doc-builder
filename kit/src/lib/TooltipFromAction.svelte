<script lang="ts">
	export let txt: string;
	export let x: number;
	export let y: number;
	export let id: string;
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

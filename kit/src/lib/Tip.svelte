<script>
	export let warning = false;
	const color = warning ? "orange" : "green";
</script>

<!-- For tailwind:
	border-green-50 text-green-700 from-green-50 dark:from-green-900 before:border-green-500 dark:before:border-green-800
	border-orange-50 text-orange-700 from-orange-50 dark:from-orange-900 before:border-orange-500 dark:before:border-orange-800
-->

<div
	class="course-tip {color === 'orange'
		? 'course-tip-orange'
		: ''} bg-gradient-to-br dark:bg-gradient-to-r before:border-{color}-500 dark:before:border-{color}-800 from-{color}-50 border to-white dark:from-gray-900 dark:to-gray-950 border-{color}-50 text-{color}-700 dark:text-gray-400"
>
	<div class="flex items-center gap-2">
		{#if warning}
			<svg
				xmlns="http://www.w3.org/2000/svg"
				width="20"
				height="20"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				stroke-linecap="round"
				stroke-linejoin="round"
				class="-mt-0.5 h-4 w-4 flex-shrink-0"
				><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3" /><path
					d="M12 9v4"
				/><path d="M12 17h.01" /></svg
			>
		{:else}
			<svg
				xmlns="http://www.w3.org/2000/svg"
				width="20"
				height="20"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				stroke-linecap="round"
				stroke-linejoin="round"
				class="-mt-0.5 h-4 w-4 flex-shrink-0"
				><path
					d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"
				/><path d="M9 18h6" /><path d="M10 22h4" /></svg
			>
		{/if}
		<div class="flex-1">
			<slot />
		</div>
	</div>
</div>

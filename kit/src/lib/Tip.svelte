<script lang="ts">
	interface IconData {
		paths: string[];
	}

	export let warning = false;
	const color: "orange" | "green" = warning ? "orange" : "green";

	// Icon paths
	const WarningIcon: IconData = {
		paths: [
			"m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3",
			"M12 9v4",
			"M12 17h.01",
		],
	};

	const TipIcon: IconData = {
		paths: [
			"M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5",
			"M9 18h6",
			"M10 22h4",
		],
	};

	const iconPaths = warning ? WarningIcon.paths : TipIcon.paths;
</script>

<div
	class="course-tip {color === 'orange'
		? 'course-tip-orange'
		: ''} border bg-gradient-to-br to-white dark:bg-gradient-to-r dark:from-gray-900 dark:to-gray-950 dark:text-gray-400 {color ===
	'orange'
		? 'border-orange-50 from-orange-50 text-orange-700 before:border-orange-500 dark:before:border-orange-800'
		: 'border-green-50 from-green-50 text-green-700 before:border-green-500 dark:before:border-green-800'}"
>
	<div class="flex items-baseline gap-2">
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
			class="h-4 w-4 flex-shrink-0 translate-y-0.5 transform"
		>
			{#each iconPaths as path}
				<path d={path} />
			{/each}
		</svg>
		<div class="mt-0.5 flex-1">
			<slot />
		</div>
	</div>
</div>

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
		: ''} bg-gradient-to-br dark:bg-gradient-to-r before:border-{color}-500 dark:before:border-{color}-800 from-{color}-50 dark:from-gray-900 to-white dark:to-gray-950 border border-{color}-50 text-{color}-700 dark:text-gray-400"
>
	<slot />
</div>

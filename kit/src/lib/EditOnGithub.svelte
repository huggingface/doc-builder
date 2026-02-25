<script lang="ts">
	import IconCode from "./IconCode.svelte";
	export let source: string = "";
</script>

<a
	class="!text-gray-400 !no-underline text-sm flex items-center not-prose mt-4"
	href={source}
	target="_blank"
>
	<IconCode classNames="mr-1" />
	<span><span class="underline">Update</span> on GitHub</span>
</a>

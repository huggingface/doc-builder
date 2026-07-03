<script lang="ts">
	interface Props {
		classNames?: string;
		label?: string;
		position?: string;
	}

	let {
		classNames = "",
		label = "Copied",
		position = "left-1/2 top-full transform -translate-x-1/2 translate-y-2",
	}: Props = $props();
</script>

<div
	class="
		absolute pointer-events-none transition-opacity bg-black text-white py-1 px-2 leading-tight rounded font-normal shadow
		{position}
		{classNames}
	"
>
	<div
		class="absolute bottom-full left-1/2 transform -translate-x-1/2 w-0 h-0 border-black border-4 border-t-0"
		style="
				border-left-color: transparent;
				border-right-color: transparent;
			"
	></div>
	{label}
</div>

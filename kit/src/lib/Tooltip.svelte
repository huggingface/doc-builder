<script>
	export let classNames = "";
	export let label = "Copied";
	export let position = "left-1/2 top-full transform -translate-x-1/2 translate-y-2";
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
	/>
	{label}
</div>

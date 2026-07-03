<script lang="ts">
	import CopyButton from "./CopyButton.svelte";
	let hideCopyButton = $state(true);
	interface Props {
		code?: string;
		highlighted?: string;
		lang?: string;
		wrap?: boolean;
		classNames?: string;
	}

	let { code = "", highlighted = "", lang = "", wrap = false, classNames = "" }: Props = $props();

	function handleMouseOver() {
		hideCopyButton = false;
	}
	function handleMouseOut() {
		hideCopyButton = true;
	}
</script>

<div
	class="code-block relative {classNames}"
	onmouseover={handleMouseOver}
	onfocus={handleMouseOver}
	onmouseout={handleMouseOut}
	onblur={handleMouseOut}
>
	<div class="absolute top-2.5 right-4">
		<CopyButton
			classNames="transition duration-200 ease-in-out {hideCopyButton && 'opacity-0'}"
			label="code excerpt"
			value={code}
		/>
	</div>
	<pre
		class="{lang ? `language-${lang}` : ''} {wrap
			? 'whitespace-pre-wrap'
			: ''}">{@html highlighted}</pre>
</div>

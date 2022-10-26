<script lang="ts">
	import { PIPELINE_DATA } from "./pipeline";
	import PipelineIcon from "./PipelineIcon.svelte";

	export let classNames = "";
	export let pipeline = "";
</script>

<div class="inline-flex items-center border pr-1 rounded-xl {classNames}">
	<PipelineIcon classNames="mr-1" {pipeline} />
	<span>
		{PIPELINE_DATA[pipeline].name ?? pipeline}
	</span>
</div>

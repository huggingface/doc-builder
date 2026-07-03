<script lang="ts">
	interface Props {
		id: string;
	}

	let { id }: Props = $props();
</script>

<iframe
	class="w-full xl:w-4/6 h-80"
	src="https://www.youtube-nocookie.com/embed/{id}"
	title="YouTube video player"
	frameborder="0"
	allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
	allowfullscreen
></iframe>

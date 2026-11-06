<script lang="ts">
	interface Props {
		classNames?: string;
	}

	let { classNames = "" }: Props = $props();
</script>

<svg
	class={classNames}
	xmlns="http://www.w3.org/2000/svg"
	aria-hidden="true"
	focusable="false"
	role="img"
	width="1em"
	height="1em"
	preserveAspectRatio="xMidYMid meet"
	viewBox="0 0 12 12"
	fill="currentColor"
>
	<rect width="9.491" height="2.438" x="1.254" y="8.845" opacity=".5" rx="1.219" />
	<path
		d="M8.068 3.07a2.678 2.678 0 0 1 0 5.355H3.932a2.678 2.678 0 0 1 0-5.355h1.652v.412a.343.343 0 0 0 .684 0V3.07zM4.412 4.85a.898.898 0 1 0 0 1.796.898.898 0 0 0 0-1.795m3.177 0a.898.898 0 1 0 0 1.796.898.898 0 0 0 0-1.795"
	/>
	<path d="M6.269 3.48a.342.342 0 0 1-.684 0V2.353a.9.9 0 0 0 .684 0z" opacity=".25" />
	<circle cx="5.927" cy="1.526" r=".894" />
</svg>

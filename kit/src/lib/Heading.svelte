<script lang="ts">
	import IconCopyLink from "./IconCopyLink.svelte";

	export let title: string;
	export let local: string;
	export let headingTag: string;
</script>

<!-- 
    using <svelte:element this="h1, ..." /> would have been cleaner but mdsvex compiler is not working
    read more: https://svelte.dev/docs/special-elements#svelte-element
 -->

{#if headingTag === "h1"}
	<h1 class="relative group">
		<a
			id={local}
			class="header-link block pr-1.5 text-lg no-hover:hidden with-hover:absolute with-hover:p-1.5 with-hover:opacity-0 with-hover:group-hover:opacity-100 with-hover:right-full"
			href="#{local}"><span><IconCopyLink /></span></a
		> <span>{title}</span>
	</h1>
{:else if headingTag === "h2"}
	<h2 class="relative group">
		<a
			id={local}
			class="header-link block pr-1.5 text-lg no-hover:hidden with-hover:absolute with-hover:p-1.5 with-hover:opacity-0 with-hover:group-hover:opacity-100 with-hover:right-full"
			href="#{local}"><span><IconCopyLink /></span></a
		> <span>{title}</span>
	</h2>
{:else if headingTag === "h3"}
	<h3 class="relative group">
		<a
			id={local}
			class="header-link block pr-1.5 text-lg no-hover:hidden with-hover:absolute with-hover:p-1.5 with-hover:opacity-0 with-hover:group-hover:opacity-100 with-hover:right-full"
			href="#{local}"><span><IconCopyLink /></span></a
		> <span>{title}</span>
	</h3>
{:else if headingTag === "h4"}
	<h4 class="relative group">
		<a
			id={local}
			class="header-link block pr-1.5 text-lg no-hover:hidden with-hover:absolute with-hover:p-1.5 with-hover:opacity-0 with-hover:group-hover:opacity-100 with-hover:right-full"
			href="#{local}"><span><IconCopyLink /></span></a
		> <span>{title}</span>
	</h4>
{:else if headingTag === "h5"}
	<h5 class="relative group">
		<a
			id={local}
			class="header-link block pr-1.5 text-lg no-hover:hidden with-hover:absolute with-hover:p-1.5 with-hover:opacity-0 with-hover:group-hover:opacity-100 with-hover:right-full"
			href="#{local}"><span><IconCopyLink /></span></a
		> <span>{title}</span>
	</h5>
{:else}
	<h6 class="relative group">
		<a
			id={local}
			class="header-link block pr-1.5 text-lg no-hover:hidden with-hover:absolute with-hover:p-1.5 with-hover:opacity-0 with-hover:group-hover:opacity-100 with-hover:right-full"
			href="#{local}"><span><IconCopyLink /></span></a
		> <span>{title}</span>
	</h6>
{/if}

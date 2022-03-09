<script lang="ts">
	import { onMount, tick } from "svelte";
	import { tooltip } from "./tooltip";
	import IconCopyLink from "./IconCopyLink.svelte";

	export let anchor: string;
	export let name: string;
	export let parameters: { name: string; val: string }[] = [];
	export let parametersDescription: {
		anchor: string;
		name: string;
		description: string;
	}[];
	export let parameterGroups: {
		title: string;
		parametersDescription: string;
	}[];
	export let returnDescription: string;
	export let returnType: string;
	export let source: string;

	let parametersElement: HTMLElement;
	let collapsed: boolean = false;

	const tooltipMapper: Record<string, string> =
		parametersDescription?.reduce((acc, element) => {
			const { name, description } = element;
			return { ...acc, [name]: description };
		}, {}) || {};

	onMount(() => {
		const { hash } = window.location;
		const containsAnchor =
			!!hash && parametersDescription?.some(({ anchor }) => anchor === hash.substring(1));

		collapsed = !containsAnchor && parametersElement.clientHeight > 500;
	});

	async function onClick(anchor: string, isAnchorExists: boolean) {
		if (isAnchorExists) {
			collapsed = false;
			await tick();
			window.location.hash = anchor;
		}
	}

	function highlightSignature(name: string) {
		if (name.startsWith("class ")) {
			// is class signature
			const signaturePath: string[] = name.substring("class ".length).split(".");
			const signatureName = signaturePath.pop();
			const signaturePrefix = signaturePath.join(".");
			return `<h3 class="!m-0"><span class="flex-1 break-all md:text-lg bg-gradient-to-r px-2.5 py-1.5 rounded-xl from-indigo-50/70 to-white dark:from-gray-900 dark:to-gray-950 dark:text-indigo-300 text-indigo-700"><svg class="mr-1.5 text-indigo-500 inline-block -mt-0.5" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" aria-hidden="true" focusable="false" role="img" width=".8em" height=".8em" preserveAspectRatio="xMidYMid meet" viewBox="0 0 24 24"><path class="uim-quaternary" d="M20.23 7.24L12 12L3.77 7.24a1.98 1.98 0 0 1 .7-.71L11 2.76c.62-.35 1.38-.35 2 0l6.53 3.77c.29.173.531.418.7.71z" opacity=".25" fill="currentColor"></path><path class="uim-tertiary" d="M12 12v9.5a2.09 2.09 0 0 1-.91-.21L4.5 17.48a2.003 2.003 0 0 1-1-1.73v-7.5a2.06 2.06 0 0 1 .27-1.01L12 12z" opacity=".5" fill="currentColor"></path><path class="uim-primary" d="M20.5 8.25v7.5a2.003 2.003 0 0 1-1 1.73l-6.62 3.82c-.275.13-.576.198-.88.2V12l8.23-4.76c.175.308.268.656.27 1.01z" fill="currentColor"></path></svg><span class="font-light">class</span> <span class="font-medium">${signaturePrefix}.</span><span class="font-semibold">${signatureName}</span></span></h3>`;
		} else {
			// is function signature
			return `<h4 class="!m-0"><span class="flex-1 rounded-xl py-0.5 break-all bg-gradient-to-r from-blue-50/60 to-white dark:from-gray-900 dark:to-gray-950 text-blue-700 dark:text-blue-300 font-medium px-2"><svg width="1em" height="1em" viewBox="0 0 32 33" class="mr-1 inline-block -mt-0.5"  xmlns="http://www.w3.org/2000/svg"><path d="M5.80566 18.3545C4.90766 17.4565 4.90766 16.0005 5.80566 15.1025L14.3768 6.53142C15.2748 5.63342 16.7307 5.63342 17.6287 6.53142L26.1999 15.1025C27.0979 16.0005 27.0979 17.4565 26.1999 18.3545L17.6287 26.9256C16.7307 27.8236 15.2748 27.8236 14.3768 26.9256L5.80566 18.3545Z" fill="currentColor" fill-opacity="0.25"/><path fill-rule="evenodd" clip-rule="evenodd" d="M16.4801 13.9619C16.4801 12.9761 16.7467 12.5436 16.9443 12.3296C17.1764 12.078 17.5731 11.8517 18.2275 11.707C18.8821 11.5623 19.638 11.5342 20.4038 11.5582C20.7804 11.57 21.1341 11.5932 21.4719 11.6156L21.5263 11.6193C21.8195 11.6389 22.1626 11.6618 22.4429 11.6618V7.40825C22.3209 7.40825 22.1219 7.39596 21.7544 7.37149C21.4202 7.34925 20.9976 7.32115 20.5371 7.30672C19.6286 7.27824 18.4672 7.29779 17.3093 7.55377C16.1512 7.8098 14.8404 8.33724 13.8181 9.4452C12.7612 10.5907 12.2266 12.1236 12.2266 13.9619V15.0127H10.6836V19.2662H12.2266V26.6332H16.4801V19.2662H20.3394V15.0127H16.4801V13.9619Z" fill="currentColor"/></svg>${name}</span></h4>`;
		}
	}

	function replaceParagraphWithSpan(txt: string): string {
		const REGEX_P = /\s*<p>(((?!<p>).)*)<\/p>\s*/gms;
		return txt.replace(REGEX_P, (_, content) => `<span>${content}</span>`);
	}
</script>

<div>
	<span
		class="group flex space-x-1.5 items-center text-gray-800 bg-gradient-to-r rounded-tr-lg -mt-4 -ml-4 pt-3 px-2.5"
		id={anchor}
	>
		{@html highlightSignature(name)}
		<a
			id={anchor}
			class="header-link invisible with-hover:group-hover:visible pr-2"
			href="#{anchor}"
		>
			<IconCopyLink />
		</a>
		<a
			class="!ml-auto !text-gray-400 !no-underline text-sm flex items-center"
			href={source}
			target="_blank"
		>
			<span>&lt;</span>
			<span class="hidden md:block mx-0.5 hover:!underline">source</span>
			<span>&gt;</span>
		</a>
	</span>
	<p class="font-mono text-xs md:text-sm !leading-relaxed !my-6">
		<span>(</span>
		{#each parameters as { name, val }}
			<span
				use:tooltip={tooltipMapper[name] || ""}
				class="comma {tooltipMapper[name] ? 'cursor-pointer' : 'cursor-default'}"
				on:click|preventDefault|stopPropagation={() =>
					onClick(`${anchor}.${name}`, !!tooltipMapper[name])}
			>
				<span
					class="rounded hover:bg-black hover:text-white dark:hover:bg-white dark:hover:text-black"
					>{name}<span class="opacity-60">{val}</span></span
				>
			</span>
		{/each}
		<span>)</span>
		{#if returnType}
			<span class="font-bold">→</span>
			<span
				use:tooltip={returnDescription || ""}
				class="rounded hover:bg-gray-400 {returnDescription ? 'cursor-pointer' : 'cursor-default'}"
				on:click|preventDefault|stopPropagation={() =>
					onClick(`${anchor}.returns`, !!returnDescription)}
				>{@html replaceParagraphWithSpan(returnType)}</span
			>
		{/if}
	</p>

	<!-- `docstring-details` class is used for crawling & populating meilisearch -->
	<div
		class="!mb-10 relative docstring-details {collapsed ? 'max-h-96 overflow-hidden' : ''}"
		bind:this={parametersElement}
	>
		{#if collapsed}
			<div
				class="absolute inset-0 bg-gradient-to-t from-white to-white/0 dark:from-gray-950 dark:to-gray-950/0 z-10 flex justify-center"
			>
				<button
					on:click={() => (collapsed = false)}
					class="absolute leading-tight px-3 py-1.5 dark:bg-gray-900 bg-black text-gray-200 hover:text-white rounded-xl bottom-12 ring-offset-2 hover:ring-black hover:ring-2"
					>Expand {parametersDescription?.length} parameters</button
				>
			</div>
		{/if}
		{#if !!parametersDescription}
			<p class="flex items-center font-semibold !mt-2 !mb-2 text-gray-800">
				Parameters <span class="flex-auto border-t-2 border-gray-100 dark:border-gray-700 ml-3" />
			</p>
			<ul class="px-2">
				{#each parametersDescription as { anchor, description }}
					<li class="text-base !pl-4 my-3">
						<span class="group flex space-x-1.5 items-start">
							<a
								id={anchor}
								class="header-link block pr-0.5 text-lg no-hover:hidden with-hover:absolute with-hover:p-1.5 with-hover:opacity-0 with-hover:group-hover:opacity-100 with-hover:right-full"
								href={`#${anchor}`}
							>
								<span><IconCopyLink classNames="text-smd" /></span>
							</a>
							<span>
								{@html description}
							</span>
						</span>
					</li>
				{/each}
			</ul>
		{/if}
		{#if parameterGroups}
			{#each parameterGroups as { title, parametersDescription }}
				<p class="flex items-center font-semibold">
					{title} <span class="flex-auto border-t-2 ml-3" />
				</p>
				<p>{@html parametersDescription}</p>
			{/each}
		{/if}
		{#if !!returnType}
			<div
				class="flex items-center font-semibold space-x-3 text-base !mt-0 !mb-0 text-gray-800"
				id={`${anchor}.returns`}
			>
				<p class="text-base">Returns</p>
				{#if !!returnType}
					{@html returnType}
				{/if}
				<span class="flex-auto border-t-2 border-gray-100 dark:border-gray-700" />
			</div>
			<p class="text-base">{@html returnDescription || ""}</p>
		{/if}
	</div>
</div>

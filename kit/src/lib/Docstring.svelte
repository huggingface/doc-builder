<script lang="ts">
	import { onMount, tick } from "svelte";
	import { tooltip } from "./tooltip";
	import IconCopyLink from "./IconCopyLink.svelte";

	type Parameter = {
		anchor: string;
		name: string;
		description: string;
	};

	export let anchor: string;
	export let name: string;
	export let parameters: { name: string; val: string }[] = [];
	export let parametersDescription: Parameter[];
	export let parameterGroups: {
		title: string;
		parametersDescription: Parameter[];
	}[];
	export let returnDescription: string;
	export let returnType: string;
	export let isYield = false;
	export let raiseDescription: string;
	export let raiseType: string;
	export let source: string | undefined = undefined;
	export let hashlink: string | undefined;
	export let isGetSetDescriptor = false;

	let parametersElement: HTMLElement;
	let containerEl: HTMLElement;
	let collapsed: boolean = false;

	const tooltipMapper: Record<string, string> =
		parametersDescription?.reduce((acc, element) => {
			const { name, description } = element;
			return { ...acc, [name]: description };
		}, {}) || {};
	const returnsTitle = isYield ? "Yields" : "Returns";
	const returnsAnchor = returnsTitle.toLowerCase();
	const bgHighlightClass = "bg-yellow-50 dark:bg-[#494a3d]";

	onMount(() => {
		const { hash } = window.location;
		hashlink = hash.substring(1);
		const hashlinksEls = parametersElement.querySelectorAll<HTMLAnchorElement>('[href^="#"]');
		const hashlinks = [...hashlinksEls].map((el) => el.id);
		const containsAnchor = hashlinks.includes(hashlink);
		collapsed = !containsAnchor && parametersElement.clientHeight > 500;
		onHashChange();
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
		} else if (isGetSetDescriptor) {
			// is @property signature (getset_descriptor)
			return `<div class="flex items-center rounded-xl py-0.5 break-all bg-gradient-to-r from-green-50/60 to-white dark:from-gray-900 dark:to-gray-950 text-green-700 dark:text-green-300 font-medium px-2"><svg class="fill-current text-2xl text-green-500 inline-block" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" aria-hidden="true" focusable="false" role="img" width="1em" height="1em" preserveAspectRatio="xMidYMid meet" viewBox="0 0 24 24"><circle cx="12.5" cy="12.5" r="7.5" fill-opacity="0.2"></circle><path d="M12.8454 17.4994C12.077 17.4994 11.3929 17.3946 10.7931 17.185C10.1933 16.9779 9.68621 16.6731 9.27188 16.2709C8.85756 15.871 8.542 15.382 8.3252 14.8039C8.1084 14.2257 8 13.5681 8 12.831C8 12.1035 8.1084 11.4435 8.3252 10.8509C8.54441 10.2583 8.86358 9.75005 9.28272 9.32608C9.70187 8.89971 10.2138 8.57211 10.8184 8.34326C11.4254 8.11442 12.1168 8 12.8924 8C13.6103 8 14.251 8.10479 14.8147 8.31436C15.3808 8.52393 15.8602 8.82263 16.2528 9.21046C16.6479 9.59588 16.9478 10.0548 17.1525 10.5871C17.3597 11.1171 17.4621 11.7036 17.4596 12.3468C17.4621 12.79 17.4235 13.1971 17.344 13.5681C17.2645 13.9391 17.1393 14.2631 16.9682 14.5401C16.7996 14.8147 16.578 15.0327 16.3034 15.1941C16.0288 15.3531 15.6963 15.4434 15.3061 15.4651C15.0267 15.4868 14.8002 15.4663 14.6268 15.4037C14.4534 15.341 14.3209 15.2483 14.2293 15.1254C14.1402 15.0002 14.0824 14.8544 14.0559 14.6882H14.0125C13.9547 14.8328 13.8415 14.9641 13.6729 15.0821C13.5043 15.1977 13.2983 15.288 13.055 15.3531C12.8141 15.4157 12.5576 15.4386 12.2854 15.4217C12.0011 15.4049 11.7313 15.3386 11.476 15.223C11.2231 15.1074 10.9978 14.94 10.8003 14.7208C10.6052 14.5015 10.451 14.2305 10.3378 13.9078C10.227 13.585 10.1704 13.2116 10.168 12.7876C10.1704 12.3685 10.2294 12.0035 10.345 11.6928C10.4631 11.3821 10.6184 11.1207 10.8112 10.9087C11.0063 10.6967 11.2231 10.5305 11.4616 10.4101C11.7 10.2896 11.9397 10.2125 12.1806 10.1788C12.4528 10.1379 12.7106 10.1379 12.9538 10.1788C13.1971 10.2198 13.4019 10.286 13.5681 10.3776C13.7367 10.4691 13.8415 10.5679 13.8825 10.6738H13.9331V10.2692H15.064V13.7957C15.0664 13.962 15.1038 14.0908 15.176 14.1824C15.2483 14.2739 15.3459 14.3197 15.4687 14.3197C15.6349 14.3197 15.7734 14.2462 15.8842 14.0993C15.9975 13.9523 16.0818 13.7271 16.1372 13.4236C16.195 13.1201 16.2239 12.7334 16.2239 12.2637C16.2239 11.8108 16.1637 11.4134 16.0432 11.0713C15.9252 10.7268 15.759 10.4342 15.5446 10.1933C15.3326 9.94998 15.0857 9.75246 14.8039 9.6007C14.522 9.44894 14.2161 9.33813 13.8861 9.26827C13.5585 9.19841 13.2212 9.16349 12.8744 9.16349C12.2745 9.16349 11.7506 9.25502 11.3026 9.4381C10.8545 9.61876 10.4811 9.8729 10.1824 10.2005C9.88374 10.5281 9.65971 10.9123 9.51036 11.3532C9.36342 11.7916 9.28875 12.2697 9.28634 12.7876C9.28875 13.3585 9.36824 13.8644 9.52482 14.3052C9.6838 14.7436 9.91746 15.1122 10.2258 15.4109C10.5341 15.7096 10.9147 15.936 11.3676 16.0902C11.8205 16.2444 12.3408 16.3215 12.9286 16.3215C13.2056 16.3215 13.4766 16.301 13.7415 16.26C14.0065 16.2215 14.2462 16.1733 14.4606 16.1155C14.675 16.0601 14.8472 16.0059 14.9773 15.9529L15.335 17.0008C15.1833 17.0875 14.9773 17.1682 14.7171 17.2428C14.4594 17.3199 14.1679 17.3814 13.8427 17.4271C13.5199 17.4753 13.1875 17.4994 12.8454 17.4994ZM12.6792 14.233C12.9731 14.233 13.2068 14.1764 13.3802 14.0631C13.5561 13.9499 13.6813 13.7825 13.756 13.5609C13.8331 13.3369 13.8692 13.061 13.8644 12.7334C13.862 12.4444 13.8247 12.1999 13.7524 11.9999C13.6825 11.7976 13.5609 11.6446 13.3874 11.541C13.2164 11.4351 12.9779 11.3821 12.672 11.3821C12.4046 11.3821 12.177 11.4387 11.9891 11.5519C11.8036 11.6651 11.6615 11.8241 11.5627 12.0288C11.4664 12.2312 11.417 12.4697 11.4146 12.7443C11.417 12.9996 11.4579 13.2417 11.5374 13.4706C11.6169 13.697 11.7482 13.8813 11.9313 14.0234C12.1144 14.1631 12.3637 14.233 12.6792 14.233Z"></path></svg><span class="text-sm text-green-500 mr-1">property</span><span> ${name}</span></div>`;
		} else {
			// is function signature
			return `<h4 class="!m-0"><span class="flex-1 rounded-xl py-0.5 break-all bg-gradient-to-r from-blue-50/60 to-white dark:from-gray-900 dark:to-gray-950 text-blue-700 dark:text-blue-300 font-medium px-2"><svg width="1em" height="1em" viewBox="0 0 32 33" class="mr-1 inline-block -mt-0.5"  xmlns="http://www.w3.org/2000/svg"><path d="M5.80566 18.3545C4.90766 17.4565 4.90766 16.0005 5.80566 15.1025L14.3768 6.53142C15.2748 5.63342 16.7307 5.63342 17.6287 6.53142L26.1999 15.1025C27.0979 16.0005 27.0979 17.4565 26.1999 18.3545L17.6287 26.9256C16.7307 27.8236 15.2748 27.8236 14.3768 26.9256L5.80566 18.3545Z" fill="currentColor" fill-opacity="0.25"/><path fill-rule="evenodd" clip-rule="evenodd" d="M16.4801 13.9619C16.4801 12.9761 16.7467 12.5436 16.9443 12.3296C17.1764 12.078 17.5731 11.8517 18.2275 11.707C18.8821 11.5623 19.638 11.5342 20.4038 11.5582C20.7804 11.57 21.1341 11.5932 21.4719 11.6156L21.5263 11.6193C21.8195 11.6389 22.1626 11.6618 22.4429 11.6618V7.40825C22.3209 7.40825 22.1219 7.39596 21.7544 7.37149C21.4202 7.34925 20.9976 7.32115 20.5371 7.30672C19.6286 7.27824 18.4672 7.29779 17.3093 7.55377C16.1512 7.8098 14.8404 8.33724 13.8181 9.4452C12.7612 10.5907 12.2266 12.1236 12.2266 13.9619V15.0127H10.6836V19.2662H12.2266V26.6332H16.4801V19.2662H20.3394V15.0127H16.4801V13.9619Z" fill="currentColor"/></svg>${name}</span></h4>`;
		}
	}

	function replaceParagraphWithSpan(txt: string): string {
		const REGEX_P = /\s*<p>(((?!<p>).)*)<\/p>\s*/gms;
		return txt.replace(REGEX_P, (_, content) => `<span>${content}</span>`);
	}

	function onHashChange() {
		const { hash } = window.location;
		hashlink = hash.substring(1);
		if (containerEl) {
			containerEl.classList.remove(...bgHighlightClass.split(" "));
		}
		if (hashlink === anchor) {
			const _containerEl = document.getElementById(hashlink)?.closest(".docstring");
			if (_containerEl) {
				containerEl = _containerEl as HTMLElement;
				containerEl.classList.add(...bgHighlightClass.split(" "));
			}
		}
	}
</script>

<svelte:window on:hashchange={onHashChange} />

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
		{#if source}
			<a
				class="!ml-auto !text-gray-400 !no-underline text-sm flex items-center"
				href={source}
				target="_blank"
			>
				<span>&lt;</span>
				<span class="hidden md:block mx-0.5 hover:!underline">source</span>
				<span>&gt;</span>
			</a>
		{/if}
	</span>
	{#if !isGetSetDescriptor}
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
					class="rounded hover:bg-gray-400 {returnDescription
						? 'cursor-pointer'
						: 'cursor-default'}"
					on:click|preventDefault|stopPropagation={() =>
						onClick(`${anchor}.${returnsAnchor}`, !!returnDescription)}
					>{@html replaceParagraphWithSpan(returnType)}</span
				>
			{/if}
		</p>
	{/if}

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
					<li class="text-base !pl-4 my-3 rounded {hashlink === anchor ? bgHighlightClass : ''}">
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
				<ul class="px-2">
					{#each parametersDescription as { anchor, description }}
						<li class="text-base !pl-4 my-3 rounded {hashlink === anchor ? bgHighlightClass : ''}">
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
			{/each}
		{/if}
		{#if !!returnType}
			<div
				id={`${anchor}.${returnsAnchor}`}
				class="flex items-center font-semibold space-x-3 text-base !mt-0 !mb-0 text-gray-800 rounded {hashlink ===
				anchor
					? bgHighlightClass
					: ''}"
			>
				<p class="text-base">{returnsTitle}</p>
				{#if !!returnType}
					{@html returnType}
				{/if}
				<span class="flex-auto border-t-2 border-gray-100 dark:border-gray-700" />
			</div>
			<p class="text-base">{@html returnDescription || ""}</p>
		{/if}
		{#if !!raiseType}
			<div
				class="flex items-center font-semibold space-x-3 text-base !mt-0 !mb-0 text-gray-800"
				id={`${anchor}.raises`}
			>
				<p class="text-base">Raises</p>
				{#if !!raiseType}
					{@html raiseType}
				{/if}
				<span class="flex-auto border-t-2 border-gray-100 dark:border-gray-700" />
			</div>
			<p class="text-base">{@html raiseDescription || ""}</p>
		{/if}
	</div>
</div>

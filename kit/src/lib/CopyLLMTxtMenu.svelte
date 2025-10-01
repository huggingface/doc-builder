<script lang="ts">
	import { browser } from "$app/environment";
	import { onDestroy, tick } from "svelte";

	export let label = "Copy page";
	export let markdownDescription = "Copy page as Markdown for LLMs";

	const DEFAULT_SOURCE_URL = "https://huggingface.co/docs/hub/storage-regions.md";

	function buildSourceUrl() {
		if (!browser) return DEFAULT_SOURCE_URL;
		const current = window.location.href.replace(/#.*$/, "");
		return current.endsWith(".md") ? current : `${current}.md`;
	}

	const SOURCE_URL = buildSourceUrl();
	const FETCH_URL = browser ? `https://r.jina.ai/${SOURCE_URL}` : undefined;
	const encodedPrompt = encodeURIComponent(
		`Read from ${SOURCE_URL} so I can ask questions about it.`
	);

	let open = false;
	let copied = false;
	let triggerEl: HTMLDivElement | null = null;
	let menuEl: HTMLDivElement | null = null;
	let menuStyle = "";
	let closeTimeout: ReturnType<typeof setTimeout> | null = null;
	let sourceMarkdown: string | null = null;
	let sourceFetchPromise: Promise<string> | null = null;

	type ExternalOption = {
		label: string;
		description: string;
		icon: "chatgpt" | "claude";
		buildUrl: () => string;
	};

	const externalOptions: ExternalOption[] = [
		{
			label: "Open in ChatGPT",
			description: "Ask questions about this page",
			icon: "chatgpt",
			buildUrl: () => `https://chatgpt.com/?hints=search&q=${encodedPrompt}`,
		},
		{
			label: "Open in Claude",
			description: "Ask questions about this page",
			icon: "claude",
			buildUrl: () => `https://claude.ai/new?q=${encodedPrompt}`,
		},
	];

	const baseMenuItemClass =
		"cursor-pointer text-sm group relative w-full select-none outline-none data-[disabled]:pointer-events-none data-[disabled]:cursor-default data-[disabled]:opacity-50 flex items-center gap-1 px-1.5 py-1.5 rounded-xl text-left transition text-gray-950/65 dark:text-white/65 hover:text-gray-950/85 dark:hover:text-white/80 focus:text-gray-950/85 dark:focus:text-white/80 focus-visible:ring-1 focus-visible:ring-primary/30 dark:focus-visible:ring-primary-light/30 bg-transparent hover:bg-gray-600/5 dark:hover:bg-gray-200/5 focus:bg-gray-600/5 dark:focus:bg-gray-200/5";

	async function loadSourceMarkdown(): Promise<string> {
		if (!browser) return "";
		if (sourceMarkdown) return sourceMarkdown;
		if (!sourceFetchPromise) {
			const target = FETCH_URL ?? SOURCE_URL;
			sourceFetchPromise = fetch(target, { headers: { Accept: "text/plain" } })
				.then((response) => {
					if (!response.ok) {
						throw new Error(`Failed to fetch source content: ${response.status}`);
					}
					return response.text();
				})
				.then((text) => {
					sourceMarkdown = text;
					return text;
				})
				.catch((error) => {
					console.error("Unable to fetch remote markdown", error);
					sourceMarkdown = "";
					return "";
				});
		}
		return sourceFetchPromise;
	}

	async function copyMarkdown() {
		if (!browser || typeof navigator === "undefined" || !navigator.clipboard) {
			console.warn("Clipboard API unavailable");
			return;
		}

		try {
			const markdown = await loadSourceMarkdown();
			if (!markdown) {
				console.warn("Nothing to copy");
				return;
			}

			await navigator.clipboard.writeText(markdown);
			copied = true;
			await tick();
			if (closeTimeout) clearTimeout(closeTimeout);
			closeTimeout = setTimeout(() => {
				copied = false;
			}, 2000);
		} catch (error) {
			console.error("Failed to write to clipboard", error);
		}
	}

	function updatePosition() {
		if (!browser || !triggerEl) return;
		const rect = triggerEl.getBoundingClientRect();
		const gutter = 10;
		const minWidth = Math.max(rect.width + 80, 220);
		const right = Math.max(window.innerWidth - rect.right, gutter);
		menuStyle = `top:${rect.bottom + gutter}px;right:${right}px;min-width:${minWidth}px;`;
	}

	function openMenu() {
		open = true;
		if (browser) {
			tick().then(updatePosition);
		}
	}

	function closeMenu() {
		open = false;
	}

	function toggleMenu() {
		open ? closeMenu() : openMenu();
	}

	function openMarkdownPreview() {
		if (browser) {
			window.open(SOURCE_URL, "_blank", "noopener,noreferrer");
		}
		closeMenu();
	}

	function launchExternal(option: ExternalOption) {
		if (browser) {
			window.open(option.buildUrl(), "_blank", "noopener,noreferrer");
		}
		closeMenu();
	}

	function handleWindowPointer(event: MouseEvent) {
		if (!open || !browser) return;
		const targetNode = event.target as Node;
		if (menuEl?.contains(targetNode) || triggerEl?.contains(targetNode)) {
			return;
		}
		closeMenu();
	}

	function handleWindowKeydown(event: KeyboardEvent) {
		if (event.key === "Escape" && open) {
			closeMenu();
		}
	}

	function handleWindowResize() {
		if (open) updatePosition();
	}

	function handleWindowScroll() {
		if (open) updatePosition();
	}

	onDestroy(() => {
		if (closeTimeout) clearTimeout(closeTimeout);
	});
</script>

<svelte:window
	on:mousedown={handleWindowPointer}
	on:keydown={handleWindowKeydown}
	on:resize={handleWindowResize}
	on:scroll={handleWindowScroll}
/>

<div class="items-center shrink-0 min-w-[156px] justify-end ml-auto flex">
	<div bind:this={triggerEl} class="inline-flex rounded-xl shadow-sm">
		<button
			on:click={copyMarkdown}
			class="inline-flex items-center gap-1.5 h-9 px-3.5 text-sm font-medium text-gray-800 dark:text-gray-100 border border-gray-200/80 dark:border-white/[0.12] border-r-0 bg-white dark:bg-[#161B26] hover:bg-gray-600/5 dark:hover:bg-gray-200/5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary/50 dark:focus-visible:outline-primary-light/50 rounded-l-xl transition-colors"
			aria-live="polite"
		>
			<span
				class="inline-flex items-center justify-center rounded-md bg-primary/10 dark:bg-primary/20 text-primary dark:text-primary-light p-1"
			>
				<svg
					width="18"
					height="18"
					viewBox="0 0 18 18"
					fill="none"
					xmlns="http://www.w3.org/2000/svg"
					class="w-4 h-4"
				>
					<path
						d="M14.25 5.25H7.25C6.14543 5.25 5.25 6.14543 5.25 7.25V14.25C5.25 15.3546 6.14543 16.25 7.25 16.25H14.25C15.3546 16.25 16.25 15.3546 16.25 14.25V7.25C16.25 6.14543 15.3546 5.25 14.25 5.25Z"
						stroke="currentColor"
						stroke-width="1.5"
						stroke-linecap="round"
						stroke-linejoin="round"
					></path>
					<path
						d="M2.80103 11.998L1.77203 5.07397C1.61003 3.98097 2.36403 2.96397 3.45603 2.80197L10.38 1.77297C11.313 1.63397 12.19 2.16297 12.528 3.00097"
						stroke="currentColor"
						stroke-width="1.5"
						stroke-linecap="round"
						stroke-linejoin="round"
					></path>
				</svg>
			</span>
			<span>{copied ? "Copied" : label}</span>
		</button>
		<button
			on:click={toggleMenu}
			class="inline-flex items-center justify-center w-9 h-9 bg-white dark:bg-[#161B26] disabled:pointer-events-none text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary/40 dark:focus-visible:outline-primary-light/40 rounded-r-xl border border-gray-200/80 dark:border-white/[0.12] border-l border-l-gray-200/80 dark:border-l-white/[0.2] hover:bg-gray-100 dark:hover:bg-gray-200/5 transition"
			aria-haspopup="menu"
			aria-expanded={open}
			aria-label={open ? "Close copy menu" : "Open copy menu"}
		>
			<svg
				width="8"
				height="24"
				viewBox="0 -9 3 24"
				class={`transition-transform text-gray-400 overflow-visible ${
					open ? "-rotate-90" : "rotate-90"
				}`}
			>
				<path
					d="M0 0L3 3L0 6"
					fill="none"
					stroke="currentColor"
					stroke-width="1.5"
					stroke-linecap="round"
					stroke-linejoin="round"
				></path>
			</svg>
		</button>
	</div>

	{#if open}
		<div
			class="fixed inset-0 z-40"
			aria-hidden="true"
			style="background: transparent;"
			on:click={closeMenu}
		></div>
		<div
			bind:this={menuEl}
			role="menu"
			class="fixed z-50 shadow-xl dark:shadow-none shadow-gray-500/5 dark:shadow-gray-900/40 bg-white/95 dark:bg-[#0F1626]/95 backdrop-blur-xl rounded-xl text-gray-950/80 dark:text-white/75 max-h-[420px] overflow-y-auto p-1 border border-gray-200/80 dark:border-white/[0.12] flex flex-col"
			style={menuStyle}
			aria-label="Copy menu"
		>
			<button
				role="menuitem"
				on:click={() => {
					copyMarkdown();
					closeMenu();
				}}
				class={baseMenuItemClass}
			>
				<div class="border border-gray-200 dark:border-white/[0.07] rounded-lg p-1.5">
					<svg
						width="18"
						height="18"
						viewBox="0 0 18 18"
						fill="none"
						xmlns="http://www.w3.org/2000/svg"
						class="w-4 h-4 shrink-0"
					>
						<path
							d="M14.25 5.25H7.25C6.14543 5.25 5.25 6.14543 5.25 7.25V14.25C5.25 15.3546 6.14543 16.25 7.25 16.25H14.25C15.3546 16.25 16.25 15.3546 16.25 14.25V7.25C16.25 6.14543 15.3546 5.25 14.25 5.25Z"
							stroke="currentColor"
							stroke-width="1.5"
							stroke-linecap="round"
							stroke-linejoin="round"
						></path>
						<path
							d="M2.80103 11.998L1.77203 5.07397C1.61003 3.98097 2.36403 2.96397 3.45603 2.80197L10.38 1.77297C11.313 1.63397 12.19 2.16297 12.528 3.00097"
							stroke="currentColor"
							stroke-width="1.5"
							stroke-linecap="round"
							stroke-linejoin="round"
						></path>
					</svg>
				</div>
				<div class="flex flex-col px-1">
					<div class="text-sm font-medium text-gray-800 dark:text-gray-300 flex items-center gap-1">
						{label}
					</div>
					<div class="text-xs text-gray-600 dark:text-gray-400">
						{markdownDescription}
					</div>
				</div>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					width="24"
					height="24"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="2.5"
					stroke-linecap="round"
					stroke-linejoin="round"
					class={`lucide lucide-check size-3.5 text-primary dark:text-primary-light transition-opacity ${
						copied ? "opacity-100" : "opacity-0"
					}`}
				>
					<path d="M20 6 9 17l-5-5"></path>
				</svg>
			</button>

			<button
				role="menuitem"
				on:click={() => {
					openMarkdownPreview();
				}}
				class={baseMenuItemClass}
			>
				<div class="border border-gray-200 dark:border-white/[0.07] rounded-lg p-1.5">
					<svg
						width="18"
						height="18"
						viewBox="0 0 18 18"
						fill="none"
						xmlns="http://www.w3.org/2000/svg"
						class="w-4 h-4 shrink-0"
					>
						<path
							d="M15.25 3.75H2.75C1.64543 3.75 0.75 4.64543 0.75 5.75V12.25C0.75 13.3546 1.64543 14.25 2.75 14.25H15.25C16.3546 14.25 17.25 13.3546 17.25 12.25V5.75C17.25 4.64543 16.3546 3.75 15.25 3.75Z"
							stroke="currentColor"
							stroke-width="1.5"
							stroke-linecap="round"
							stroke-linejoin="round"
						></path>
						<path
							d="M8.75 11.25V6.75H8.356L6.25 9.5L4.144 6.75H3.75V11.25"
							stroke="currentColor"
							stroke-width="1.5"
							stroke-linecap="round"
							stroke-linejoin="round"
						></path>
						<path
							d="M11.5 9.5L13.25 11.25L15 9.5"
							stroke="currentColor"
							stroke-width="1.5"
							stroke-linecap="round"
							stroke-linejoin="round"
						></path>
						<path
							d="M13.25 11.25V6.75"
							stroke="currentColor"
							stroke-width="1.5"
							stroke-linecap="round"
							stroke-linejoin="round"
						></path>
					</svg>
				</div>
				<div class="flex flex-col px-1">
					<div class="text-sm font-medium text-gray-800 dark:text-gray-300 flex items-center gap-1">
						View as Markdown
						<svg
							xmlns="http://www.w3.org/2000/svg"
							width="24"
							height="24"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							stroke-width="1.75"
							stroke-linecap="round"
							stroke-linejoin="round"
							class="lucide lucide-arrow-up-right w-4 h-4 text-gray-500 dark:text-gray-300 shrink-0"
						>
							<path d="M7 7h10v10"></path>
							<path d="M7 17 17 7"></path>
						</svg>
					</div>
					<div class="text-xs text-gray-600 dark:text-gray-400">View this page as plain text</div>
				</div>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					width="24"
					height="24"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="2.5"
					stroke-linecap="round"
					stroke-linejoin="round"
					class="lucide lucide-check size-3.5 text-primary dark:text-primary-light opacity-0"
				>
					<path d="M20 6 9 17l-5-5"></path>
				</svg>
			</button>

			{#each externalOptions as option}
				<button role="menuitem" on:click={() => launchExternal(option)} class={baseMenuItemClass}>
					<div class="border border-gray-200 dark:border-white/[0.07] rounded-lg p-1.5">
						{#if option.icon === "chatgpt"}
							<svg
								fill="currentColor"
								fill-rule="evenodd"
								height="1em"
								viewBox="0 0 24 24"
								width="1em"
								xmlns="http://www.w3.org/2000/svg"
								class="w-4 h-4 shrink-0"
							>
								<title>OpenAI</title>
								<path
									d="M21.55 10.004a5.416 5.416 0 00-.478-4.501c-1.217-2.09-3.662-3.166-6.05-2.66A5.59 5.59 0 0010.831 1C8.39.995 6.224 2.546 5.473 4.838A5.553 5.553 0 001.76 7.496a5.487 5.487 0 00.691 6.5 5.416 5.416 0 00.477 4.502c1.217 2.09 3.662 3.165 6.05 2.66A5.586 5.586 0 0013.168 23c2.443.006 4.61-1.546 5.361-3.84a5.553 5.553 0 003.715-2.66 5.488 5.488 0 00-.693-6.497v.001zm-8.381 11.558a4.199 4.199 0 01-2.675-.954c.034-.018.093-.05.132-.074l4.44-2.53a.71.71 0 00.364-.623v-6.176l1.877 1.069c.02.01.033.029.036.05v5.115c-.003 2.274-1.87 4.118-4.174 4.123zM4.192 17.78a4.059 4.059 0 01-.498-2.763c.032.02.09.055.131.078l4.44 2.53c.225.13.504.13.73 0l5.42-3.088v2.138a.068.068 0 01-.027.057L9.9 19.288c-1.999 1.136-4.552.46-5.707-1.51h-.001zM3.023 8.216A4.15 4.15 0 015.198 6.41l-.002.151v5.06a.711.711 0 00.364.624l5.42 3.087-1.876 1.07a.067.067 0 01-.063.005l-4.489-2.559c-1.995-1.14-2.679-3.658-1.53-5.63h.001zm15.417 3.54l-5.42-3.088L14.896 7.6a.067.067 0 01.063-.006l4.489 2.557c1.998 1.14 2.683 3.662 1.529 5.633a4.163 4.163 0 01-2.174 1.807V12.38a.71.71 0 00-.363-.623zm1.867-2.773a6.04 6.04 0 00-.132-.078l-4.44-2.53a.731.731 0 00-.729 0l-5.42 3.088V7.325a.068.068 0 01.027-.057L14.1 4.713c2-1.137 4.555-.46 5.707 1.513.487.833.664 1.809.499 2.757h.001zm-11.741 3.81l-1.877-1.068a.065.065 0 01-.036-.051V6.559c.001-2.277 1.873-4.122 4.181-4.12.976 0 1.92.338 2.671.954-.034.018-.092.05-.131.073l-4.44 2.53a.71.71 0 00-.365.623l-.003 6.173v.002zm1.02-2.168L12 9.25l2.414 1.375v2.75L12 14.75l-2.415-1.375v-2.75z"
								></path>
							</svg>
						{:else}
							<svg
								fill="currentColor"
								height="1em"
								viewBox="0 0 24 24"
								width="1em"
								xmlns="http://www.w3.org/2000/svg"
								class="w-4 h-4 shrink-0"
							>
								<title>Anthropic</title>
								<path
									d="M13.827 3.52h3.603L24 20h-3.603l-6.57-16.48zm-7.258 0h3.767L16.906 20h-3.674l-1.343-3.461H5.017l-1.344 3.46H0L6.57 3.522zm4.132 9.959L8.453 7.687 6.205 13.48H10.7z"
								></path>
							</svg>
						{/if}
					</div>
					<div class="flex flex-col px-1">
						<div
							class="text-sm font-medium text-gray-800 dark:text-gray-200 flex items-center gap-1"
						>
							{option.label}
						</div>
						<div class="text-xs text-gray-600 dark:text-gray-400">
							{option.description}
						</div>
					</div>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						width="24"
						height="24"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="1.75"
						stroke-linecap="round"
						stroke-linejoin="round"
						class="lucide lucide-arrow-up-right w-4 h-4 text-gray-500 dark:text-gray-300"
					>
						<path d="M7 7h10v10" />
						<path d="M7 17 17 7" />
					</svg>
				</button>
			{/each}
		</div>
	{/if}
</div>

<script lang="ts">
	import { onDestroy, tick } from "svelte";
	import { copyToClipboard } from "./copyToClipboard";
	import IconCopy from "./IconCopy.svelte";
	import IconCaret from "./IconCaret.svelte";
	import IconCode from "./IconCode.svelte";
	import IconArrowUpRight from "./IconArrowUpRight.svelte";
	import IconOpenAI from "./IconOpenAI.svelte";
	import IconAnthropic from "./IconAnthropic.svelte";
	import IconMCP from "./IconMCP.svelte";

	export let label = "Copy page";
	export let markdownDescription = "Copy page as Markdown for LLMs";
	export let containerClass = "";
	export let containerStyle = "";

	const isClient = typeof window !== "undefined";
	const hasDocument = typeof document !== "undefined";

	function resolveSourceUrl() {
		if (!isClient || !window.location) return;
		const current = window.location.href.replace(/#.*$/, "");
		return current;
	}

	const SOURCE_URL = resolveSourceUrl() ?? "";
	const SOURCE_URL_MD = SOURCE_URL.endsWith(".md") ? SOURCE_URL : SOURCE_URL + ".md";
	let encodedPrompt: string | null = null;

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
		icon: "chatgpt" | "claude" | "mcp";
		buildUrl: () => string;
	};

	const externalOptions: ExternalOption[] = [
		{
			label: "Open in ChatGPT",
			description: "Ask questions about this page",
			icon: "chatgpt",
			buildUrl: () =>
				encodedPrompt
					? `https://chatgpt.com/?hints=search&q=${encodedPrompt}`
					: "https://chatgpt.com",
		},
		{
			label: "Open in Claude",
			description: "Ask questions about this page",
			icon: "claude",
			buildUrl: () =>
				encodedPrompt ? `https://claude.ai/new?q=${encodedPrompt}` : "https://claude.ai/new",
		},
		{
			label: "Connect to MCP Client",
			description: "Install MCP server on Cursor, VS Code, etc.",
			icon: "mcp",
			buildUrl: () => "https://huggingface.co/mcp",
		},
	];

	const baseMenuItemClass =
		"cursor-pointer text-sm group relative w-full select-none outline-none flex items-center gap-1 px-1.5 py-1.5 rounded-xl text-left transition border-gray-200 bg-white hover:shadow-inner dark:border-gray-850 dark:bg-gray-950 dark:text-gray-200 dark:hover:bg-gray-800";

	function ensurePromptAndUrl() {
		if (encodedPrompt || !isClient) return;
		encodedPrompt = encodeURIComponent(`Read from ${SOURCE_URL} so I can ask questions about it.`);
	}

	async function fetchSourceMarkdown(): Promise<string> {
		if (!isClient || typeof fetch !== "function" || !SOURCE_URL) return "";
		ensurePromptAndUrl();
		if (sourceMarkdown) return sourceMarkdown;
		if (!sourceFetchPromise) {
			sourceFetchPromise = fetch(SOURCE_URL, { headers: { Accept: "text/plain" } })
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
		if (!isClient) {
			console.warn("Clipboard API unavailable");
			return;
		}

		try {
			const markdown = await fetchSourceMarkdown();
			if (!markdown) {
				console.warn("Nothing to copy");
				return;
			}

			const hasNavigatorClipboard =
				typeof navigator !== "undefined" &&
				!!navigator.clipboard &&
				typeof navigator.clipboard.writeText === "function";

			if (hasNavigatorClipboard) {
				await navigator.clipboard.writeText(markdown);
			} else if (hasDocument) {
				copyToClipboard(markdown);
			} else {
				console.warn("Clipboard API unavailable");
				return;
			}

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

	function openMenu() {
		open = true;
		if (isClient && triggerEl) {
			void tick().then(() => {
				if (!triggerEl) return;
				const rect = triggerEl.getBoundingClientRect();
				const gutter = 10;
				const minWidth = Math.max(rect.width + 80, 220);
				const right = Math.max(window.innerWidth - rect.right, gutter);
				menuStyle = `top:${rect.bottom + gutter}px;right:${right}px;min-width:${minWidth}px;`;
			});
		}
	}

	function closeMenu() {
		open = false;
	}

	function toggleMenu() {
		open ? closeMenu() : openMenu();
	}

	function openMarkdownPreview() {
		if (!isClient) return;
		window.open(SOURCE_URL_MD, "_blank", "noopener,noreferrer");
		closeMenu();
	}

	function launchExternal(option: ExternalOption) {
		ensurePromptAndUrl();
		if (isClient) {
			window.open(option.buildUrl(), "_blank", "noopener,noreferrer");
		}
		closeMenu();
	}

	function handleWindowPointer(event: MouseEvent) {
		if (!open || !isClient) return;
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
		if (open) closeMenu();
	}

	function handleWindowScroll() {
		if (open) closeMenu();
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

<div
	class={`items-center shrink-0 min-w-[100px] max-sm:min-w-[50px] justify-end ml-auto flex${
		containerClass ? ` ${containerClass}` : ""
	}`}
	style={containerStyle}
>
	<div bind:this={triggerEl} class="inline-flex rounded-md max-sm:rounded-sm">
		<button
			on:click={copyMarkdown}
			class="inline-flex items-center gap-1 max-sm:gap-0.5 h-6 max-sm:h-5 px-2 max-sm:px-1.5 text-[11px] max-sm:text-[9px] font-medium text-gray-800 border border-r-0 rounded-l-md max-sm:rounded-l-sm border-gray-200 bg-white hover:shadow-inner dark:border-gray-850 dark:bg-gray-950 dark:text-gray-200 dark:hover:bg-gray-800"
			aria-live="polite"
		>
			<span class="inline-flex items-center justify-center rounded-md p-0.5 max-sm:p-0">
				<IconCopy classNames="w-3 h-3 max-sm:w-2.5 max-sm:h-2.5" />
			</span>
			<span>{copied ? "Copied" : label}</span>
		</button>
		<button
			on:click={toggleMenu}
			class="inline-flex items-center justify-center w-6 max-sm:w-5 h-6 max-sm:h-5 disabled:pointer-events-none text-sm text-gray-500 hover:text-gray-700 dark:hover:text-white rounded-r-md max-sm:rounded-r-sm border border-l transition border-gray-200 bg-white hover:shadow-inner dark:border-gray-850 dark:bg-gray-950 dark:text-gray-200 dark:hover:bg-gray-800"
			aria-haspopup="menu"
			aria-expanded={open}
			aria-label={open ? "Close copy menu" : "Open copy menu"}
		>
			<IconCaret
				classNames={`transition-transform text-gray-400 overflow-visible w-3 h-3 max-sm:w-2.5 max-sm:h-2.5 ${
					open ? "rotate-180" : "rotate-0"
				}`}
			/>
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
			class="fixed z-50 backdrop-blur-xl rounded-xl max-h-[420px] overflow-y-auto p-1 border flex flex-col border-gray-200 bg-white dark:border-gray-850 dark:bg-gray-950 dark:text-gray-200"
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
				<div class="border border-gray-200 dark:border-gray-850 rounded-lg p-1.5">
					<IconCopy classNames="w-4 h-4 shrink-0" />
				</div>
				<div class="flex flex-col px-1">
					<div class="text-sm font-medium text-gray-800 dark:text-gray-300 flex items-center gap-1">
						{label}
					</div>
					<div class="text-xs text-gray-600 dark:text-gray-400">
						{markdownDescription}
					</div>
				</div>
			</button>

			<button
				role="menuitem"
				on:click={() => {
					openMarkdownPreview();
				}}
				class={baseMenuItemClass}
			>
				<div class="border border-gray-200 dark:border-gray-850 rounded-lg p-1.5">
					<IconCode classNames="w-4 h-4 shrink-0" />
				</div>
				<div class="flex flex-col px-1">
					<div class="text-sm font-medium text-gray-800 dark:text-gray-300 flex items-center gap-1">
						View as Markdown
						<IconArrowUpRight classNames="w-4 h-4 text-gray-500 dark:text-gray-300 shrink-0" />
					</div>
					<div class="text-xs text-gray-600 dark:text-gray-400">View this page as plain text</div>
				</div>
			</button>

			{#each externalOptions as option}
				<button role="menuitem" on:click={() => launchExternal(option)} class={baseMenuItemClass}>
					<div class="border border-gray-200 dark:border-gray-850 rounded-lg p-1.5">
						{#if option.icon === "chatgpt"}
							<IconOpenAI classNames="w-4 h-4 shrink-0" />
						{:else if option.icon === "claude"}
							<IconAnthropic classNames="w-4 h-4 shrink-0" />
						{:else if option.icon === "mcp"}
							<IconMCP classNames="w-4 h-4 shrink-0" />
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
					<IconArrowUpRight classNames="w-4 h-4 text-gray-500 dark:text-gray-300" />
				</button>
			{/each}
		</div>
	{/if}
</div>

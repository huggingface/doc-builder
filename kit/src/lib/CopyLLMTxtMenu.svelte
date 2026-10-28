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
	import IconHuggingChat from "./IconHuggingChat.svelte";
	import { copyMenuStrings } from "./copyMenuStrings";

	interface Props {
		label?: string;
		markdownDescription?: string;
		containerClass?: string;
		containerStyle?: string;
	}

	const isClient = typeof window !== "undefined";
	const hasDocument = typeof document !== "undefined";
	const t = copyMenuStrings(isClient ? window.location.pathname : "");

	let {
		label = t.copyPage,
		markdownDescription = t.copyPageDescription,
		containerClass = "",
		containerStyle = "",
	}: Props = $props();

	function resolveSourceUrl() {
		if (!isClient || !window.location) return;
		const current = window.location.href.replace(/#.*$/, "");
		return current;
	}

	const SOURCE_URL = resolveSourceUrl() ?? "";
	const SOURCE_URL_MD = SOURCE_URL.endsWith(".md") ? SOURCE_URL : SOURCE_URL + ".md";
	let encodedPrompt: string | null = null;

	let open = $state(false);
	let copied = $state(false);
	let triggerEl: HTMLDivElement | null = $state(null);
	let menuEl: HTMLDivElement | null = $state(null);
	let menuStyle = $state("");
	// in right-to-left pages, the menu is laid out right-to-left too
	let rtl = $state(false);
	let closeTimeout: ReturnType<typeof setTimeout> | null = null;
	let sourceMarkdown: string | null = null;
	let sourceFetchPromise: Promise<string> | null = null;

	type ExternalOption = {
		label: string;
		description: string;
		icon: "chatgpt" | "claude" | "mcp" | "huggingchat";
		buildUrl: () => string;
	};

	const externalOptions: ExternalOption[] = [
		{
			label: t.openIn("HuggingChat"),
			description: t.askQuestions,
			icon: "huggingchat",
			buildUrl: () => {
				const encodedAttachment = encodeURIComponent(SOURCE_URL_MD);
				const encodedPromptText = encodeURIComponent(
					`Read from ${SOURCE_URL} so I can ask questions about it.`
				);
				return `https://huggingface.co/chat/?attachments=${encodedAttachment}&prompt=${encodedPromptText}`;
			},
		},
		{
			label: t.openIn("ChatGPT"),
			description: t.askQuestions,
			icon: "chatgpt",
			buildUrl: () =>
				encodedPrompt
					? `https://chatgpt.com/?hints=search&q=${encodedPrompt}`
					: "https://chatgpt.com",
		},
		{
			label: t.openIn("Claude"),
			description: t.askQuestions,
			icon: "claude",
			buildUrl: () =>
				encodedPrompt ? `https://claude.ai/new?q=${encodedPrompt}` : "https://claude.ai/new",
		},
		{
			label: t.connectMcp,
			description: t.connectMcpDescription,
			icon: "mcp",
			buildUrl: () => "https://huggingface.co/mcp",
		},
	];

	const baseMenuItemClass =
		"cursor-pointer text-sm group relative w-full select-none outline-none flex items-center gap-1 px-1.5 py-1.5 rounded-xl text-start transition border-gray-200 bg-white hover:shadow-inner dark:border-gray-850 dark:bg-gray-950 dark:text-gray-200 dark:hover:bg-gray-800";

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
		rtl = !!triggerEl?.closest('[dir="rtl"]');
		ensurePromptAndUrl();
		if (isClient) void positionMenu();
	}

	async function positionMenu() {
		await tick();
		if (!triggerEl) return;
		const rect = triggerEl.getBoundingClientRect();
		const gutter = 10;
		const size = `min-width:${Math.max(rect.width + 80, 220)}px;max-width:${window.innerWidth - 2 * gutter}px;`;
		menuStyle = `top:${rect.bottom + gutter}px;left:0;visibility:hidden;${size}`;
		await tick();
		if (!menuEl) return;
		const width = menuEl.getBoundingClientRect().width;
		// Open towards the page content: leftwards from the trigger's right edge, or rightwards from its
		// left edge in right-to-left pages (where the trigger sits at the left, next to the sidebar).
		const left = Math.max(
			gutter,
			Math.min(rtl ? rect.left : rect.right - width, window.innerWidth - gutter - width)
		);
		menuStyle = `top:${rect.bottom + gutter}px;left:${left}px;${size}`;
	}

	function closeMenu() {
		open = false;
	}

	function toggleMenu() {
		open ? closeMenu() : openMenu();
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
	onmousedown={handleWindowPointer}
	onkeydown={handleWindowKeydown}
	onresize={handleWindowResize}
	onscroll={handleWindowScroll}
/>

<div
	class={`items-center shrink-0 min-w-[100px] max-sm:min-w-[50px] justify-end ml-auto flex${
		containerClass ? ` ${containerClass}` : ""
	}`}
	style={containerStyle}
>
	<!-- the button pair keeps its order and rounded corners in right-to-left pages -->
	<div bind:this={triggerEl} dir="ltr" class="inline-flex rounded-md max-sm:rounded-sm">
		<button
			onclick={copyMarkdown}
			class="inline-flex items-center gap-1 h-7 max-sm:h-7 px-2 max-sm:px-1.5 text-sm font-medium text-gray-800 border border-r-0 rounded-l-md max-sm:rounded-l-sm border-gray-200 bg-white hover:shadow-inner dark:border-gray-850 dark:bg-gray-950 dark:text-gray-200 dark:hover:bg-gray-800"
			aria-live="polite"
		>
			<span
				class="inline-flex items-center justify-center rounded-md p-0.5 max-sm:p-0 hover:text-gray-800 dark:hover:text-gray-200"
			>
				<IconCopy classNames="sm:size-3.5 size-3" />
			</span>
			<span dir="auto">{copied ? t.copied : label}</span>
		</button>
		<button
			onclick={toggleMenu}
			class="inline-flex items-center justify-center w-6 max-sm:w-5 h-7 max-sm:h-7 disabled:pointer-events-none text-sm text-gray-500 hover:text-gray-700 dark:hover:text-white rounded-r-md max-sm:rounded-r-sm border border-l transition border-gray-200 bg-white hover:shadow-inner dark:border-gray-850 dark:bg-gray-950 dark:text-gray-200 dark:hover:bg-gray-800"
			aria-haspopup="menu"
			aria-expanded={open}
			aria-label={open ? t.closeMenu : t.openMenu}
		>
			<IconCaret
				classNames={`transition-transform text-gray-400 overflow-visible sm:size-3.5 size-3 ${
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
			onclick={closeMenu}
		></div>
		<div
			bind:this={menuEl}
			role="menu"
			dir={rtl ? "rtl" : undefined}
			class="fixed z-50 backdrop-blur-xl rounded-xl max-h-[420px] overflow-y-auto p-1 border flex flex-col border-gray-200 bg-white dark:border-gray-850 dark:bg-gray-950 dark:text-gray-200"
			style={menuStyle}
			aria-label={t.menu}
		>
			<button
				role="menuitem"
				onclick={() => {
					copyMarkdown();
					closeMenu();
				}}
				class={baseMenuItemClass}
			>
				<div class="border border-gray-200 dark:border-gray-850 rounded-lg p-1.5">
					<IconCopy classNames="w-4 h-4 shrink-0" />
				</div>
				<div class="flex flex-col flex-1 min-w-0 px-1" dir="auto">
					<div class="text-sm font-medium text-gray-800 dark:text-gray-300 flex items-center gap-1">
						{label}
					</div>
					<div class="text-xs text-gray-600 dark:text-gray-400">
						{markdownDescription}
					</div>
				</div>
			</button>

			<a
				role="menuitem"
				href={SOURCE_URL_MD}
				target="_blank"
				rel="noopener noreferrer"
				onclick={closeMenu}
				class="{baseMenuItemClass} no-underline!"
			>
				<div class="border border-gray-200 dark:border-gray-850 rounded-lg p-1.5">
					<IconCode classNames="w-4 h-4 shrink-0" />
				</div>
				<div class="flex flex-col flex-1 min-w-0 px-1" dir="auto">
					<div class="text-sm font-medium text-gray-800 dark:text-gray-300 flex items-center gap-1">
						{t.viewMarkdown}
						<IconArrowUpRight classNames="w-4 h-4 text-gray-500 dark:text-gray-300 shrink-0" />
					</div>
					<div class="text-xs text-gray-600 dark:text-gray-400">{t.viewMarkdownDescription}</div>
				</div>
			</a>

			{#each externalOptions as option}
				<a
					role="menuitem"
					href={option.buildUrl()}
					target="_blank"
					rel="noopener noreferrer"
					onclick={closeMenu}
					class="{baseMenuItemClass} no-underline!"
				>
					<div class="border border-gray-200 dark:border-gray-850 rounded-lg p-1.5">
						{#if option.icon === "huggingchat"}
							<IconHuggingChat classNames="w-4 h-4 shrink-0" />
						{:else if option.icon === "chatgpt"}
							<IconOpenAI classNames="w-4 h-4 shrink-0" />
						{:else if option.icon === "claude"}
							<IconAnthropic classNames="w-4 h-4 shrink-0" />
						{:else if option.icon === "mcp"}
							<IconMCP classNames="w-4 h-4 shrink-0" />
						{/if}
					</div>
					<div class="flex flex-col flex-1 min-w-0 px-1" dir="auto">
						<div
							class="text-sm font-medium text-gray-800 dark:text-gray-200 flex items-center gap-1"
						>
							{option.label}
						</div>
						<div class="text-xs text-gray-600 dark:text-gray-400">
							{option.description}
						</div>
					</div>
					<IconArrowUpRight classNames="w-4 h-4 text-gray-500 dark:text-gray-300 shrink-0" />
				</a>
			{/each}
		</div>
	{/if}
</div>

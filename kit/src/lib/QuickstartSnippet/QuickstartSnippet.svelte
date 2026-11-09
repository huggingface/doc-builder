<script lang="ts">
	import hljs from "highlight.js";
	import { onMount, type Component } from "svelte";
	import { base } from "$app/paths";

	import { copyToClipboard } from "$lib/copyToClipboard";
	import IconCode from "$lib/IconCode.svelte";
	import IconCopy from "$lib/IconCopy.svelte";
	import IconClaudeCode from "./IconClaudeCode.svelte";
	import IconCodex from "./IconCodex.svelte";
	import IconHermesAgent from "./IconHermesAgent.svelte";
	import IconOpenCode from "./IconOpenCode.svelte";
	import IconPi from "./IconPi.svelte";
	import { routerModels, type RouterModel } from "./routerModels";
	import {
		AGENT_STEPS,
		API_CODE,
		FORMATS,
		INSTALL,
		LANGS,
		MODELS,
		SURFACES,
		TOKEN_URL,
		type Format,
		type Lang,
		type Surface,
	} from "./snippets";

	const STORAGE_KEY = "inference-providers-quickstart";
	const DOCS_URL = "https://huggingface.co/docs/inference-providers";

	const ICONS: Record<Surface, Component<{ classNames?: string }>> = {
		api: IconCode,
		"claude-code": IconClaudeCode,
		codex: IconCodex,
		opencode: IconOpenCode,
		pi: IconPi,
		hermes: IconHermesAgent,
	};

	// tailwind classes only: kit's CSS is emptied in production builds and the hub's CSS styles the docs, so
	// every class used here must exist in moon-landing's build (see its DocPage/TailwindWhitelist.svelte)
	const TEXT_MUTED = "text-gray-500 dark:text-gray-400";
	const TEXT_STRONG = "text-gray-900 dark:text-gray-100";
	const BORDER = "border-gray-200 dark:border-gray-800";
	const CODE_BG = "bg-gray-50 dark:bg-gray-900";

	let surface = $state<Surface>("api");
	let format = $state<Format>("chat");
	let lang = $state<Lang>("python");
	let model = $state(MODELS[0].id);
	let live = $state<RouterModel>();
	/** Key of the block that was just copied, to show "Copied" on its button */
	let copied = $state<string>();
	let copiedTimeout: ReturnType<typeof setTimeout>;

	let modelLabel = $derived(MODELS.find((m) => m.id === model)?.label ?? model);
	/** The HF SDKs have no cURL snippet: show Python instead */
	let codeLang = $derived<Lang>(API_CODE[format][lang] ? lang : "python");
	let code = $derived(API_CODE[format][codeLang]!(model));
	let install = $derived(INSTALL[format][codeLang]);
	let steps = $derived(surface === "api" ? [] : AGENT_STEPS[surface](model, modelLabel));
	let docsPath = $derived(
		surface === "api"
			? FORMATS.find((f) => f.id === format)!.docs
			: SURFACES.find((s) => s.id === surface)!.docs!
	);

	let liveProviders = $derived(live?.providers.filter((p) => p.status === "live") ?? []);
	let minOutputPrice = $derived(
		Math.min(
			...liveProviders
				.map((p) => p.pricing?.output)
				.filter((n): n is number => typeof n === "number")
		)
	);
	let maxContext = $derived(Math.max(0, ...liveProviders.map((p) => p.context_length ?? 0)));

	onMount(() => {
		const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
		surface = SURFACES.some((s) => s.id === saved.surface) ? saved.surface : surface;
		format = FORMATS.some((f) => f.id === saved.format) ? saved.format : format;
		lang = LANGS.some((l) => l.id === saved.lang) ? saved.lang : lang;
		model = MODELS.some((m) => m.id === saved.model) ? saved.model : model;
		return () => clearTimeout(copiedTimeout);
	});

	$effect(() => {
		const id = model;
		routerModels().then((models) => {
			if (id === model) {
				live = models.get(id);
			}
		});
	});

	function select(update: () => void) {
		update();
		localStorage.setItem(STORAGE_KEY, JSON.stringify({ surface, format, lang, model }));
	}

	function copy(key: string, text: string) {
		copyToClipboard(text);
		copied = key;
		clearTimeout(copiedTimeout);
		copiedTimeout = setTimeout(() => (copied = undefined), 1200);
	}

	function highlight(text: string, language: string): string {
		// bash renders the JSON body of `curl -d '{...}'` as one string: highlight it as JSON
		const curlBody = language === "bash" && text.match(/^([\s\S]*?-d )'(\{[\s\S]*\})'$/);
		if (curlBody) {
			const [, head, body] = curlBody;
			return `${hljs.highlight(head, { language }).value}'${hljs.highlight(body, { language: "json" }).value}'`;
		}
		return hljs.highlight(text, { language }).value;
	}

	const escapeHtml = (s: string) =>
		s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);

	/** Step texts use Markdown's `code` and **bold** */
	const inlineHtml = (s: string) =>
		escapeHtml(s)
			.replace(
				/`([^`]+)`/g,
				`<code class="rounded bg-gray-100 px-1 py-0.5 font-mono text-xs ${TEXT_STRONG} dark:bg-gray-800">$1</code>`
			)
			.replace(/\*\*([^*]+)\*\*/g, `<b class="font-semibold ${TEXT_STRONG}">$1</b>`);

	const formatPrice = (n: number) => (n < 1 ? `$${n.toFixed(2)}` : `$${n.toFixed(n % 1 ? 2 : 0)}`);

	const formatContext = (n: number) =>
		n >= 1e6 ? `${Math.round(n / 1e5) / 10}M` : `${Math.round(n / 1e3)}K`;

	async function agentPrompt(): Promise<string> {
		const lines: string[] = [];
		if (surface === "api") {
			const label = `${FORMATS.find((f) => f.id === format)!.label}, ${LANGS.find((l) => l.id === codeLang)!.label}`;
			lines.push(
				`# Call ${model} with Hugging Face Inference Providers (${label})`,
				"",
				`Create a Hugging Face token with the "Make calls to Inference Providers" permission at ${TOKEN_URL}, then set it as \`HF_TOKEN\` in the environment.`,
				""
			);
			if (install) {
				lines.push("```bash", install, "```", "");
			}
			lines.push("```" + LANGS.find((l) => l.id === codeLang)!.hl, code, "```", "");
		} else {
			lines.push(
				`# Set up ${SURFACES.find((s) => s.id === surface)!.label} with Hugging Face Inference Providers (${model})`,
				""
			);
			steps.forEach((step, i) => {
				lines.push(`## ${i + 1}. ${step.title}`, "");
				if (step.text) {
					lines.push(step.text, "");
				}
				if (step.link) {
					lines.push(step.link.href, "");
				}
				if (step.code) {
					lines.push("```" + (step.hl === "ini" ? "toml" : step.hl), step.code, "```", "");
				}
			});
		}
		lines.push(
			"Append `:fastest`, `:cheapest` or a provider name (e.g. `:novita`) to the model id to change routing.",
			""
		);
		const providers = (await routerModels()).get(model)?.providers.length;
		if (providers) {
			lines.push(`Model: https://huggingface.co/${model} (${providers} providers)`);
		}
		lines.push(
			"Models list: https://router.huggingface.co/v1/models",
			`Docs: ${DOCS_URL}/${docsPath}.md`
		);
		return lines.join("\n");
	}
</script>

{#snippet copyButton(key: string, text: string, classNames: string)}
	<button
		type="button"
		title="Copy"
		class="absolute rounded-md border bg-white px-2 py-0.5 text-xs dark:bg-gray-950 {BORDER} {TEXT_MUTED} hover:text-gray-900 dark:hover:text-gray-100 {classNames}"
		onclick={() => copy(key, text)}
	>
		{copied === key ? "Copied" : "Copy"}
	</button>
{/snippet}

<div class="not-prose my-6 rounded-2xl border bg-white p-2 shadow-sm dark:bg-gray-950 {BORDER}">
	<div class="flex flex-col gap-2 md:flex-row">
		<div class="flex shrink-0 gap-0.5 overflow-x-auto md:flex-col" role="tablist">
			{#each SURFACES as s}
				{@const Icon = ICONS[s.id]}
				{#if s.id === "claude-code"}
					<div
						class="hidden px-2.5 pb-1 pt-3 text-xs font-bold uppercase tracking-wide md:block {TEXT_MUTED}"
					>
						Coding agents
					</div>
				{/if}
				<button
					type="button"
					role="tab"
					aria-selected={surface === s.id}
					class="flex items-center gap-2 whitespace-nowrap rounded-lg px-2 py-1.5 text-left text-sm {surface ===
					s.id
						? `bg-gray-50 font-semibold ring-1 ring-gray-200 dark:bg-gray-900 dark:ring-gray-800 ${TEXT_STRONG}`
						: `hover:bg-gray-50 dark:hover:bg-gray-900 ${TEXT_MUTED}`}"
					onclick={() => select(() => (surface = s.id))}
				>
					<span class="flex size-5 shrink-0 items-center justify-center {TEXT_STRONG}">
						<Icon classNames="size-5" />
					</span>
					{s.label}
				</button>
			{/each}
		</div>

		<div class="min-w-0 flex-1 overflow-hidden rounded-xl border {BORDER}">
			{#if surface === "api"}
				<div
					class="flex flex-wrap items-center justify-between gap-2 border-b p-1.5 {BORDER} {CODE_BG}"
				>
					<div class="flex flex-wrap gap-0.5">
						{#each FORMATS as f}
							<button
								type="button"
								class="whitespace-nowrap rounded-md px-2.5 py-1 text-sm {format === f.id
									? `bg-white font-semibold shadow-sm ring-1 ring-gray-200 dark:bg-gray-950 dark:ring-gray-800 ${TEXT_STRONG}`
									: `hover:text-gray-900 dark:hover:text-gray-100 ${TEXT_MUTED}`}"
								onclick={() => select(() => (format = f.id))}
							>
								{f.label}
							</button>
						{/each}
					</div>
					<div
						class="flex shrink-0 overflow-hidden rounded-lg border bg-white dark:bg-gray-950 {BORDER}"
					>
						{#each LANGS as l}
							{@const disabled = !API_CODE[format][l.id]}
							<button
								type="button"
								{disabled}
								title={disabled ? "The HF SDKs are Python and JavaScript" : undefined}
								class="px-2.5 py-1 text-xs {codeLang === l.id
									? 'bg-gray-900 font-semibold text-white dark:bg-gray-100 dark:text-gray-900'
									: disabled
										? `cursor-not-allowed opacity-40 ${TEXT_MUTED}`
										: `hover:text-gray-900 dark:hover:text-gray-100 ${TEXT_MUTED}`}"
								onclick={() => select(() => (lang = l.id))}
							>
								{l.label}
							</button>
						{/each}
					</div>
				</div>
				{#if install}
					<div
						class="border-b border-dashed px-4 py-1.5 font-mono text-xs {BORDER} {CODE_BG} {TEXT_MUTED}"
					>
						$ {install}
					</div>
				{/if}
				<div class="relative {CODE_BG}" style="min-height: 19rem">
					{@render copyButton("code", code, "right-2.5 top-2.5")}
					<pre
						class="overflow-x-auto p-4 font-mono text-sm leading-relaxed text-gray-800 dark:text-gray-200"><code
							>{@html highlight(code, LANGS.find((l) => l.id === codeLang)!.hl)}</code
						></pre>
				</div>
			{:else}
				<ol class="overflow-y-auto px-4 pt-4" style="max-height: 27rem">
					{#each steps as step, i}
						<li class="relative flex gap-3.5 pb-4">
							{#if i < steps.length - 1}
								<span class="absolute bottom-1 left-3 top-8 w-px bg-gray-200 dark:bg-gray-800"
								></span>
							{/if}
							<span
								class="flex size-6 shrink-0 items-center justify-center rounded-full border border-gray-300 bg-white text-xs dark:border-gray-700 dark:bg-gray-950 {TEXT_MUTED}"
							>
								{i + 1}
							</span>
							<div class="min-w-0 flex-1">
								<div class="text-sm font-semibold leading-6 {TEXT_STRONG}">{step.title}</div>
								{#if step.text}
									<p class="text-sm {TEXT_MUTED}">{@html inlineHtml(step.text)}</p>
								{/if}
								{#if step.link}
									<a
										href={step.link.href}
										target="_blank"
										rel="noopener noreferrer"
										class="mt-2 block rounded-full border border-gray-300 py-1.5 text-center text-sm font-semibold hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-900 {TEXT_STRONG}"
									>
										{step.link.label} ↗
									</a>
								{/if}
								{#if step.code}
									<div class="group relative mt-2 rounded-lg border {BORDER} {CODE_BG}">
										{@render copyButton(
											`step-${i}`,
											step.code,
											"right-1.5 top-1.5 opacity-0 transition-opacity group-hover:opacity-100"
										)}
										<pre
											class="overflow-x-auto px-3.5 py-2 font-mono text-sm leading-relaxed text-gray-800 dark:text-gray-200"><code
												>{@html highlight(step.code, step.hl!)}</code
											></pre>
									</div>
								{/if}
							</div>
						</li>
					{/each}
				</ol>
			{/if}
			<div class="flex flex-wrap items-center justify-between gap-2.5 border-t p-2 {BORDER}">
				<button
					type="button"
					class="inline-flex items-center gap-1.5 whitespace-nowrap rounded-lg border bg-white px-3 py-1.5 text-sm font-semibold hover:bg-gray-50 dark:bg-gray-950 dark:hover:bg-gray-900 {BORDER} {TEXT_STRONG}"
					onclick={async () => copy("agent", await agentPrompt())}
				>
					<IconCopy classNames="size-3.5" />
					{copied === "agent" ? "Copied" : "Copy for agent"}
				</button>
				<div class="flex gap-4 whitespace-nowrap text-sm">
					<a
						href="https://huggingface.co/{model}"
						target="_blank"
						rel="noopener noreferrer"
						class="hover:text-gray-900 dark:hover:text-gray-100 {TEXT_MUTED}">Model page ↗</a
					>
					<a
						href="{base}/{docsPath}"
						class="hover:text-gray-900 dark:hover:text-gray-100 {TEXT_MUTED}">Read docs →</a
					>
				</div>
			</div>
		</div>
	</div>

	<div class="flex flex-wrap gap-2 px-1 pb-1 pt-3">
		{#each MODELS as m}
			<button
				type="button"
				title={m.id}
				class="inline-flex items-center gap-1.5 rounded-full border bg-white py-0.5 pl-0.5 pr-3 text-sm dark:bg-gray-950 {model ===
				m.id
					? `border-gray-900 font-semibold ring-4 ring-yellow-100 dark:border-gray-100 dark:ring-amber-700/50 ${TEXT_STRONG}`
					: `hover:border-gray-300 dark:hover:border-gray-700 ${BORDER} ${TEXT_STRONG}`}"
				onclick={() => select(() => (model = m.id))}
			>
				<img src={m.avatar} alt="" class="size-5 rounded-full bg-white" />
				{m.label}
			</button>
		{/each}
		<a
			href="https://huggingface.co/inference/models"
			target="_blank"
			rel="noopener noreferrer"
			class="inline-flex items-center px-2 text-sm hover:text-gray-900 dark:hover:text-gray-100 {TEXT_MUTED}"
		>
			All models ↗
		</a>
	</div>

	<div
		class="flex min-h-7 flex-wrap items-center gap-x-3 gap-y-1 px-2 pb-1 pt-2 text-xs {TEXT_MUTED}"
	>
		{#if liveProviders.length}
			<span
				><b class="font-semibold {TEXT_STRONG}">{liveProviders.length}</b>
				provider{liveProviders.length > 1 ? "s" : ""}</span
			>
			{#if Number.isFinite(minOutputPrice)}
				<span
					>from <b class="font-semibold {TEXT_STRONG}">{formatPrice(minOutputPrice)}</b> / M output tokens</span
				>
			{/if}
			{#if maxContext}
				<span><b class="font-semibold {TEXT_STRONG}">{formatContext(maxContext)}</b> context</span>
			{/if}
			{#if liveProviders.some((p) => p.supports_tools)}
				<span>tool calling</span>
			{/if}
			{#if live?.architecture?.input_modalities?.includes("image")}
				<span>vision</span>
			{/if}
			<span class="ml-auto text-green-600" title="Live from GET /v1/models">● live</span>
		{/if}
	</div>
</div>

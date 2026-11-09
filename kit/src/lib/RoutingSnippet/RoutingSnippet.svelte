<script lang="ts">
	import { onMount } from "svelte";

	import { providerName, routerModels, type RouterProvider } from "$lib/routerModels";

	/** One request through the router for each routing goal, with the live providers of `MODEL` */
	const MODEL = "deepseek-ai/DeepSeek-V4.1-Flash";
	const STORAGE_KEY = "inference-providers-routing";

	type Mode = "balanced" | "cost" | "speed";

	const MODES: { id: Mode; label: string; suffix: string; caption: string }[] = [
		{
			id: "balanced",
			label: "Balanced",
			suffix: "default",
			caption:
				"OpenRouter picks a provider from its measured price, speed and reliability, and retries on another one if it fails.",
		},
		{
			id: "cost",
			label: "Cost",
			suffix: ":cheapest",
			caption: "Picks the provider with the lowest price.",
		},
		{
			id: "speed",
			label: "Speed",
			suffix: ":fastest",
			caption: "Picks the provider with the highest throughput, in tokens per second.",
		},
	];

	// The animation is SMIL, not CSS: kit's CSS is emptied in production builds and the hub's CSS styles
	// the docs, so only tailwind classes that exist in moon-landing's build can be used here
	/** Seconds: the request reaches the router, then the provider; on a failover, the retry starts after */
	const T_ROUTER = 0.35;
	const T_HOP = 0.45;
	const T_RETRY = T_ROUTER + T_HOP + 0.25;

	let mode = $state<Mode>("balanced");
	let providers = $state<RouterProvider[]>();
	let unavailable = $state(false);
	let animated = $state(false);
	/** Bumped to replay the animation */
	let play = $state(0);
	let root: HTMLDivElement;

	/** Up to 4 providers, always including the fastest, the second fastest and the cheapest */
	let picked = $derived.by(() => {
		const candidates = (providers ?? []).filter(
			(p) => p.status === "live" && p.pricing && p.throughput
		);
		const bySpeed = [...candidates].sort((a, b) => b.throughput! - a.throughput!);
		const cheapest = [...candidates].sort((a, b) => a.pricing!.output - b.pricing!.output)[0];
		const list = [...new Set([bySpeed[0], bySpeed[1], cheapest, ...bySpeed])]
			.filter(Boolean)
			.slice(0, 4);
		return { list, fastest: bySpeed[0], second: bySpeed[1], cheapest };
	});
	let target = $derived(
		mode === "cost"
			? picked.cheapest
			: mode === "speed"
				? picked.fastest
				: (picked.second ?? picked.fastest)
	);
	let failed = $derived(mode === "balanced" && picked.second ? picked.fastest : undefined);
	let height = $derived(12 + picked.list.length * 62);
	let midY = $derived(height / 2);
	let arrival = $derived(failed ? T_RETRY + T_HOP : T_ROUTER + T_HOP);

	const providerY = (i: number) => 6 + i * 62 + 25;
	const curve = (y: number) => `M410,${midY} C470,${midY} 470,${y} 530,${y}`;

	function metric(p: RouterProvider): string {
		if (mode === "cost") {
			return `$${+p.pricing!.output.toFixed(3)} / M out`;
		}
		if (mode === "speed") {
			return `${Math.round(p.throughput!)} tok/s`;
		}
		return "";
	}

	function replay() {
		animated = !matchMedia("(prefers-reduced-motion: reduce)").matches;
		play++;
	}

	onMount(() => {
		const saved = localStorage.getItem(STORAGE_KEY);
		mode = MODES.some((m) => m.id === saved) ? (saved as Mode) : mode;
		let observer: IntersectionObserver | undefined;
		routerModels().then((models) => {
			providers = models.get(MODEL)?.providers;
			unavailable = !providers;
			observer = new IntersectionObserver(
				([entry]) => {
					if (entry.isIntersecting) {
						observer?.disconnect();
						replay();
					}
				},
				{ threshold: 0.5 }
			);
			observer.observe(root);
		});
		return () => observer?.disconnect();
	});
</script>

<div
	bind:this={root}
	class="not-prose my-6 rounded-2xl border border-gray-200 bg-white px-4 pb-3 pt-4 dark:border-gray-800 dark:bg-gray-950"
>
	<div class="flex flex-wrap items-start justify-between gap-x-4 gap-y-2.5">
		<div class="max-w-md">
			<div class="text-lg font-bold text-gray-900 dark:text-gray-100">
				Choose how requests are routed
			</div>
			<p class="mt-0.5 min-h-11 text-sm text-gray-500 dark:text-gray-400">
				{MODES.find((m) => m.id === mode)!.caption}
			</p>
		</div>
		<div
			class="flex gap-0.5 rounded-lg border border-gray-200 bg-gray-50 p-0.5 dark:border-gray-800 dark:bg-gray-900"
			role="tablist"
		>
			{#each MODES as m}
				<button
					type="button"
					role="tab"
					aria-selected={mode === m.id}
					class="flex flex-col items-center rounded-md px-2.5 py-1 text-sm leading-tight {mode ===
					m.id
						? 'bg-white font-semibold text-gray-900 ring-1 ring-gray-200 dark:bg-gray-950 dark:text-gray-100 dark:ring-gray-800'
						: 'text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100'}"
					onclick={() => {
						mode = m.id;
						localStorage.setItem(STORAGE_KEY, mode);
						replay();
					}}
				>
					{m.label}
					<span class="font-mono text-xs font-normal">{m.suffix}</span>
				</button>
			{/each}
		</div>
	</div>

	<div class="mt-3 min-h-44">
		{#if !picked.list.length}
			<div class="py-16 text-center text-sm text-gray-500 dark:text-gray-400">
				{unavailable ? "Live providers are unavailable right now" : "Loading live providers…"}
			</div>
		{:else}
			{#key play}
				<svg
					viewBox="0 0 760 {height}"
					class="block h-auto w-full"
					role="img"
					aria-label="Request routing diagram"
				>
					{#snippet hop(d: string, begin: number)}
						<circle
							r="3.5"
							fill="currentColor"
							class="text-gray-900 dark:text-gray-100"
							opacity="0"
						>
							<set attributeName="opacity" to="1" begin="{begin}s" />
							<animateMotion
								dur="{T_HOP}s"
								begin="{begin}s"
								fill="freeze"
								path={d}
								calcMode="spline"
								keyTimes="0;1"
								keySplines=".4 0 .2 1"
							/>
							<set attributeName="opacity" to="0" begin="{begin + T_HOP}s" />
						</circle>
					{/snippet}

					{#snippet draw(begin: number)}
						<animate
							attributeName="stroke-dashoffset"
							from="1"
							to="0"
							begin="{begin}s"
							dur="{T_HOP}s"
							fill="freeze"
							calcMode="spline"
							keyTimes="0;1"
							keySplines=".4 0 .2 1"
						/>
					{/snippet}

					{#snippet fadeIn(begin: number, to = 1)}
						<animate
							attributeName="opacity"
							from="0"
							{to}
							begin="{begin}s"
							dur="0.25s"
							fill="freeze"
						/>
					{/snippet}
					<path
						d="M140,{midY} L220,{midY}"
						pathLength="1"
						fill="none"
						stroke="currentColor"
						stroke-width="1.75"
						class="text-gray-900 dark:text-gray-100"
						stroke-dasharray={animated ? 1 : undefined}
						stroke-dashoffset={animated ? 1 : undefined}
					>
						{#if animated}{@render draw(0)}{/if}
					</path>
					{#each picked.list as p, i}
						{#if p === target}
							<path
								d={curve(providerY(i))}
								pathLength="1"
								fill="none"
								stroke="currentColor"
								stroke-width="1.75"
								class="text-gray-900 dark:text-gray-100"
								stroke-dasharray={animated ? 1 : undefined}
								stroke-dashoffset={animated ? 1 : undefined}
							>
								{#if animated}{@render draw(failed ? T_RETRY : T_ROUTER)}{/if}
							</path>
						{:else if p === failed}
							<path
								d={curve(providerY(i))}
								pathLength="1"
								fill="none"
								stroke="currentColor"
								stroke-width="1.5"
								stroke-dasharray="0.006 0.008"
								class="text-red-500"
								opacity={animated ? 0 : 0.7}
							>
								{#if animated}{@render fadeIn(T_ROUTER, 0.7)}{/if}
							</path>
						{:else}
							<path
								d={curve(providerY(i))}
								fill="none"
								stroke="currentColor"
								stroke-width="1.5"
								class="text-gray-200 dark:text-gray-800"
							/>
						{/if}
					{/each}

					<rect
						x="20"
						y={midY - 24}
						width="120"
						height="48"
						rx="10"
						fill="none"
						stroke="currentColor"
						class="text-gray-300 dark:text-gray-700"
					/>
					<text
						x="80"
						y={midY + 5}
						text-anchor="middle"
						font-size="14"
						font-weight="600"
						fill="currentColor"
						class="text-gray-900 dark:text-gray-100">Your app</text
					>
					<rect
						x="220"
						y={midY - 28}
						width="190"
						height="56"
						rx="10"
						fill="none"
						stroke="currentColor"
						class="text-gray-900 dark:text-gray-100"
					/>
					<text
						x="315"
						y={midY - 3}
						text-anchor="middle"
						font-size="14"
						font-weight="600"
						fill="currentColor"
						class="text-gray-900 dark:text-gray-100">router.huggingface.co</text
					>
					<text
						x="315"
						y={midY + 15}
						text-anchor="middle"
						font-size="12"
						fill="currentColor"
						class="font-mono text-gray-500 dark:text-gray-400"
						>{MODEL.split("/")[1]}{mode === "balanced"
							? ""
							: MODES.find((m) => m.id === mode)!.suffix}</text
					>

					{#each picked.list as p, i}
						{@const y = providerY(i) - 25}
						{@const status = p === failed ? "unavailable" : metric(p)}
						{@const begin = p === failed ? T_ROUTER + T_HOP : arrival}
						<rect
							x="530"
							{y}
							width="210"
							height="50"
							rx="10"
							fill="none"
							stroke="currentColor"
							stroke-dasharray={p === failed ? "4 3" : undefined}
							class={p === target
								? "text-green-600"
								: p === failed
									? "text-red-500"
									: "text-gray-300 dark:text-gray-700"}
						/>
						<text
							x="546"
							y={y + (status ? 21 : 30)}
							font-size="14"
							font-weight="600"
							fill="currentColor"
							class="text-gray-900 dark:text-gray-100">{providerName(p.provider)}</text
						>
						{#if status}
							<text
								x="546"
								y={y + 38}
								font-size="12"
								fill="currentColor"
								class="font-mono {p === failed
									? 'text-red-500'
									: 'text-gray-500 dark:text-gray-400'}">{status}</text
							>
						{/if}
						{#if p === target || p === failed}
							<text
								x="722"
								y={y + 30}
								text-anchor="end"
								font-size="15"
								font-weight="700"
								fill="currentColor"
								class={p === target ? "text-green-600" : "text-red-500"}
								opacity={animated ? 0 : 1}
								>{p === target ? "✓" : "✕"}{#if animated}{@render fadeIn(begin)}{/if}</text
							>
						{/if}
					{/each}

					{#if animated}
						{@render hop(`M140,${midY} L220,${midY}`, 0)}
						{#if failed}
							{@render hop(curve(providerY(picked.list.indexOf(failed))), T_ROUTER)}
						{/if}
						{@render hop(
							curve(providerY(picked.list.indexOf(target!))),
							failed ? T_RETRY : T_ROUTER
						)}
					{/if}
				</svg>
			{/key}
		{/if}
	</div>

	<div class="mt-1.5 text-xs text-gray-500 dark:text-gray-400">
		Live providers of <a
			href="https://huggingface.co/{MODEL}"
			target="_blank"
			rel="noopener noreferrer"
			class="underline">{MODEL}</a
		>
	</div>
</div>

<script lang="ts">
	import hljs from "highlight.js";
	import type {
		InferenceSnippetLanguage,
		ModelDataMinimal,
		PipelineType,
	} from "@huggingface/tasks";
	import { type InferenceProvider, snippets } from "@huggingface/inference";
	import { onMount, SvelteComponent } from "svelte";

	import CodeBlock from "$lib/CodeBlock.svelte";
	import IconCurl from "$lib/IconCurl.svelte";
	import IconJs from "$lib/IconJs.svelte";
	import IconPython from "$lib/IconPython.svelte";

	import IconInferenceBlackForest from "./IconInferenceBlackForest.svelte";
	import IconInferenceCerebras from "./IconInferenceCerebras.svelte";
	import IconInferenceCohere from "./IconInferenceCohere.svelte";
	import IconInferenceFal from "./IconInferenceFal.svelte";
	import IconInferenceFeatherless from "./IconInferenceFeatherless.svelte";
	import IconInferenceFireworks from "./IconInferenceFireworks.svelte";
	import IconInferenceGroq from "./IconInferenceGroq.svelte";
	import IconInferenceHf from "./IconInferenceHf.svelte";
	import IconInferenceHyperbolic from "./IconInferenceHyperbolic.svelte";
	import IconInferenceNebius from "./IconInferenceNebius.svelte";
	import IconInferenceNovita from "./IconInferenceNovita.svelte";
	import IconInferenceNscale from "./IconInferenceNscale.svelte";
	import IconInferenceReplicate from "./IconInferenceReplicate.svelte";
	import IconInferenceSambaNova from "./IconInferenceSambaNova.svelte";
	import IconInferenceTogetherAI from "./IconInferenceTogetherAI.svelte";
	import Dropdown from "$lib/Dropdown.svelte";
	import DropdownEntry from "$lib/DropdownEntry.svelte";
	import IconSettings from "./IconSettings.svelte";
	import IconLinkExternal from "./IconLinkExternal.svelte";

	type InferenceProviderNotOpenAI = Exclude<InferenceProvider, "openai">;

	export let pipeline: PipelineType;
	export let conversational = false;
	export let providersMapping: Partial<
		Record<
			InferenceProviderNotOpenAI,
			{
				modelId: string;
				providerModelId: string;
			}
		>
	> = {};

	let providers = Object.keys(providersMapping) as InferenceProviderNotOpenAI[];
	let selectedProvider = providers[0];
	let streaming = false;

	const model = {
		id: providersMapping[selectedProvider]!.modelId,
		pipeline_tag: pipeline,
		tags: conversational ? ["conversational"] : [],
	};
	const accessToken = "hf_xxxxxxxxxxxxxxxxxxxxxxxx";

	const availableSnippets = snippets.getInferenceSnippets(
		model as ModelDataMinimal,
		accessToken,
		selectedProvider,
		{
			hfModelId: providersMapping[selectedProvider]!.modelId,
			providerId: providersMapping[selectedProvider]!.providerModelId,
			status: "live",
			task: pipeline,
		}
	);
	const languages = [...new Set(availableSnippets.map((s) => s.language))];
	let selectedLanguage = languages[0];
	const clientsByLanguage = Object.fromEntries(
		languages.map((lang) => [
			lang,
			[...new Set(availableSnippets.filter((s) => s.language === lang).map((s) => s.client))],
		])
	);
	$: clients = clientsByLanguage[selectedLanguage];
	$: selectedClient = clients?.[0];

	$: code = snippets
		.getInferenceSnippets(
			model as ModelDataMinimal,
			accessToken,
			selectedProvider,
			{
				hfModelId: providersMapping[selectedProvider]!.modelId,
				providerId: providersMapping[selectedProvider]!.providerModelId,
				status: "live",
				task: pipeline,
			},
			{
				streaming,
			}
		)
		.find((s) => s.language === selectedLanguage && s.client === selectedClient)?.content;

	const PRETTY_NAMES: Record<InferenceProviderNotOpenAI | InferenceSnippetLanguage, string> = {
		// inference providers
		"black-forest-labs": "Black Forest Labs",
		cerebras: "Cerebras",
		cohere: "Cohere",
		"fal-ai": "fal",
		"featherless-ai": "Featherless",
		"fireworks-ai": "Fireworks",
		groq: "Groq",
		hyperbolic: "Hyperbolic",
		nebius: "Nebius AI Studio",
		novita: "Novita",
		nscale: "Nscale",
		replicate: "Replicate",
		sambanova: "SambaNova",
		together: "Together AI",
		"hf-inference": "HF Inference API",
		// languages
		sh: "cURL",
		python: "Python",
		js: "JavaScript",
		// clients
	};

	const ICONS: Record<
		InferenceProviderNotOpenAI | InferenceSnippetLanguage,
		new (...args: any) => SvelteComponent
	> = {
		// inference providers
		"black-forest-labs": IconInferenceBlackForest,
		cerebras: IconInferenceCerebras,
		cohere: IconInferenceCohere,
		"fal-ai": IconInferenceFal,
		"featherless-ai": IconInferenceFeatherless,
		"fireworks-ai": IconInferenceFireworks,
		groq: IconInferenceGroq,
		hyperbolic: IconInferenceHyperbolic,
		nebius: IconInferenceNebius,
		novita: IconInferenceNovita,
		nscale: IconInferenceNscale,
		replicate: IconInferenceReplicate,
		sambanova: IconInferenceSambaNova,
		together: IconInferenceTogetherAI,
		"hf-inference": IconInferenceHf,
		// languages
		sh: IconCurl,
		python: IconPython,
		js: IconJs,
		// clients
	};

	const base64 = (val: string) => btoa(encodeURIComponent(val));

	onMount(() => {
		// shuffle providers
		providers = providers.sort(() => Math.random() - 0.5);
		selectedProvider = providers[0];
	});
</script>

<div
	class="flex gap-x-2 justify-between md:items-top w-full text-sm not-prose flex-col md:flex-row"
>
	<!-- Language selection -->
	{#if languages.length > 1}
		<div>
			<p class="font-mono text-xs opacity-50 hidden md:block">Language</p>
			<div class="my-1.5 flex items-center gap-x-1 gap-y-0.5 flex-wrap">
				{#each languages as language}
					<button
						class="text-md flex select-none items-center rounded-lg border px-1.5 py-1 leading-none
                                {selectedLanguage === language
							? 'border-gray-800 bg-black text-white dark:bg-gray-700'
							: 'hover:shadow-xs cursor-pointer text-gray-500 opacity-90 hover:text-gray-700 dark:hover:text-gray-200'}"
						type="button"
						on:click={() => (selectedLanguage = language)}
					>
						{#if ICONS[language]}
							<svelte:component this={ICONS[language]} classNames="mr-1.5 text-current" />
						{/if}
						{PRETTY_NAMES[language] ?? language}
					</button>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Client selection -->
	{#if clients.length > 1}
		<div>
			<p class="font-mono text-xs opacity-50 hidden md:block">Client</p>
			<div class="my-1.5 flex items-center gap-x-1 gap-y-0.5 flex-wrap">
				{#each clients as client}
					<button
						class="text-md flex select-none items-center rounded-lg border px-1.5 py-1 leading-none
                                {selectedClient === client
							? 'border-gray-800 bg-black text-white dark:bg-gray-700'
							: 'hover:shadow-xs cursor-pointer text-gray-500 opacity-90 hover:text-gray-700 dark:hover:text-gray-200'}"
						type="button"
						on:click={() => (selectedClient = client)}
					>
						{client}
					</button>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Provider selection -->
	{#if providers.length > 0}
		{@const nVisibleProviders = 2}
		<div>
			<p class="font-mono text-xs opacity-50 hidden md:block">Provider</p>
			<div class="my-1.5 flex items-center gap-x-1 gap-y-0.5 flex-wrap">
				{#each providers.slice(0, nVisibleProviders) as provider}
					<button
						class="text-md flex select-none items-center rounded-lg border px-1.5 py-1 leading-none
                            {selectedProvider === provider
							? 'border-gray-800 bg-black text-white dark:bg-gray-700'
							: 'hover:shadow-xs cursor-pointer text-gray-500 opacity-90 hover:text-gray-700 dark:hover:text-gray-200'}"
						type="button"
						on:click={() => (selectedProvider = provider)}
					>
						{#if ICONS[provider]}
							<svelte:component this={ICONS[provider]} classNames="mr-1.5 text-current" />
						{/if}
						{PRETTY_NAMES[provider] ?? provider}
					</button>
				{/each}
				{#if providers.length > nVisibleProviders}
					<Dropdown btnLabel="" classNames="colab-dropdown" noBtnClass useDeprecatedJS={false}>
						<slot slot="button">
							<p
								class="text-md flex select-none items-center rounded-lg border px-1.5 py-1 leading-none hover:shadow-xs cursor-pointer text-gray-500 opacity-90 hover:text-gray-700 dark:hover:text-gray-200"
							>
								+{providers.length - nVisibleProviders}
							</p>
						</slot>
						<slot slot="menu">
							{#each providers.slice(nVisibleProviders) as provider, idx}
								<DropdownEntry
									classNames="text-sm !no-underline"
									iconClassNames="mr-1.5 text-current"
									icon={ICONS[provider]}
									label={PRETTY_NAMES[provider] ?? provider}
									useDeprecatedJS={false}
									onClick={() => {
										selectedProvider = provider;
										providers = [
											selectedProvider,
											...providers.filter((p) => p !== selectedProvider),
										];
									}}
								/>
							{/each}
						</slot>
					</Dropdown>
				{/if}
			</div>
		</div>
	{/if}

	<div>
		<p class="font-mono text-xs invisible hidden md:block">Settings</p>
		<div class="flex not-prose my-1.5">
			<Dropdown
				btnLabel=""
				classNames="hidden md:block"
				noBtnClass
				useDeprecatedJS={false}
				forceMenuAlignement="right"
			>
				<slot slot="button">
					<button
						class="text-md flex select-none items-center rounded-lg border px-1.5 py-1 leading-none hover:shadow-xs cursor-pointer text-gray-500 opacity-90 hover:text-gray-700 dark:hover:text-gray-200"
						type="button"
						title="Settings dropdown"
					>
						<IconSettings classNames="mr-1" />
						Settings
					</button>
				</slot>
				<slot slot="menu">
					<div class="flex flex-col p-2 gap-y-2">
						{#if model.tags.includes("conversational")}
							<button
								class="text-md group relative flex items-center self-start leading-tight gap-x-2 border-b w-full pb-2 cursor-default do-not-close-dropdown"
								on:click={() => (streaming = !streaming)}
								type="button"
							>
								<input
									class="form-input not-prose do-not-close-dropdown"
									type="checkbox"
									bind:checked={streaming}
									id="stream-checkbox"
								/>
								<span class="do-not-close-dropdown">Stream</span>
							</button>
						{/if}
						<a
							href="https://huggingface.co/settings/tokens"
							class="whitespace-nowrap flex gap-x-1 items-center"
							target="_blank"
							title="Tokens settings"
						>
							<IconLinkExternal /> Manage tokens
						</a>

						<a
							href="https://huggingface.co/settings/inference-providers"
							class="whitespace-nowrap flex gap-x-1 items-center"
							title="Inference providers settings"
							target="_blank"
						>
							<IconLinkExternal /> Manage providers
						</a>
					</div>
				</slot>
			</Dropdown>
			<Dropdown
				classNames="md:hidden"
				noBtnClass
				useDeprecatedJS={false}
				forceMenuAlignement="left"
			>
				<slot slot="button">
					<button
						class="text-md flex select-none items-center rounded-lg border px-1.5 py-1 leading-none hover:shadow-xs cursor-pointer text-gray-500 opacity-90 hover:text-gray-700 dark:hover:text-gray-200"
						type="button"
						title="Settings dropdown"
					>
						<IconSettings classNames="mr-1" />
						Settings
					</button>
				</slot>
				<slot slot="menu">
					<div class="flex flex-col p-2 gap-y-2">
						{#if model.tags.includes("conversational")}
							<button
								class="text-md group relative flex items-center self-start leading-tight gap-x-2 border-b w-full pb-2 cursor-default do-not-close-dropdown"
								on:click={() => (streaming = !streaming)}
								type="button"
							>
								<input
									class="form-input not-prose do-not-close-dropdown"
									type="checkbox"
									bind:checked={streaming}
								/>
								<span class="do-not-close-dropdown">Stream</span>
							</button>
						{/if}
						<a
							href="/settings/tokens"
							class="whitespace-nowrap flex gap-x-1 items-center"
							target="_blank"
							title="Tokens settings"
						>
							<IconLinkExternal /> Manage tokens
						</a>

						<a
							href="/settings/inference-providers"
							class="whitespace-nowrap flex gap-x-1 items-center"
							title="Inference providers settings"
							target="_blank"
						>
							<IconLinkExternal /> Manage providers
						</a>
					</div>
				</slot>
			</Dropdown>
			<div class="flex-grow md:hidden" />
		</div>
	</div>
</div>

{#if code}
	<CodeBlock code={base64(code)} highlighted={hljs.highlight(selectedLanguage, code, true).value} />
{/if}

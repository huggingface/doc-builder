<script lang="ts">
    import hljs from "highlight.js";
	import type { ModelDataMinimal, PipelineType } from "@huggingface/tasks";
	import { type InferenceProvider, snippets } from "@huggingface/inference";

	import CodeBlock from "$lib/CodeBlock.svelte";
    import IconCaretDown from "$lib/IconCaretDown.svelte";
	import IconCurl from "$lib/IconCurl.svelte";
	import IconJs from "$lib/IconJs.svelte";
	import IconPython from "$lib/IconPython.svelte";

    import IconInferenceBlackForest from './IconInferenceBlackForest.svelte';
    import IconInferenceCerebras from './IconInferenceCerebras.svelte';
    import IconInferenceCohere from './IconInferenceCohere.svelte';
    import IconInferenceFal from './IconInferenceFal.svelte';
    import IconInferenceFireworks from './IconInferenceFireworks.svelte';
    import IconInferenceHf from './IconInferenceHf.svelte';
    import IconInferenceHyperbolic from './IconInferenceHyperbolic.svelte';
    import IconInferenceNebius from './IconInferenceNebius.svelte';
    import IconInferenceNovita from './IconInferenceNovita.svelte';
    import IconInferenceReplicate from './IconInferenceReplicate.svelte';
    import IconInferenceSambaNova from './IconInferenceSambaNova.svelte';
    import IconInferenceTogetherAI from './IconInferenceTogetherAI.svelte';

    export let modelId: string;
    export let pipeline: PipelineType;
    export let conversational = false;
    export let providers: InferenceProvider[] = [];

    let selectedProvider = providers[0];
    let streaming = false;

    const model = {
        id: modelId,
        pipeline_tag: pipeline,
        tags: conversational ? ["conversational"] : [],
    };
    const accessToken = "hf_xxxxxxxxxxxxxxxxxxxxxxxx"

    const availableSnippets = snippets.getInferenceSnippets(model as ModelDataMinimal, accessToken, selectedProvider);
    const languages = [...new Set(availableSnippets.map(s => s.language))];
    let selectedLanguage = languages[0];
    const clientsByLanguage = Object.fromEntries(
        languages.map(lang => [
            lang,
            [...new Set(availableSnippets
                .filter(s => s.language === lang)
                .map(s => s.client))]
        ])
    );
    $: clients = clientsByLanguage[selectedLanguage];
    $: selectedClient = clients?.[0];


    $: code = snippets.getInferenceSnippets(model as ModelDataMinimal, accessToken, selectedProvider, undefined, {streaming}).find(s => s.language === selectedLanguage && s.client === selectedClient)?.content;

    const PRETTY_NAMES: Record<string, string> = {
        // inference providers
        'black-forest-labs': 'Black Forest',
        'cerebras': 'Cerebras',
        'cohere': 'Cohere',
        'fal-ai': 'FAL',
        'fireworks-ai': 'Fireworks',
        'hf-inference': 'HuggingFace',
        'hyperbolic': 'Hyperbolic',
        'nebius': 'Nebius',
        'novita': 'Novita',
        'openai': 'OpenAI',
        'replicate': 'Replicate',
        'sambanova': 'SambaNova',
        'together': 'Together AI',
        // languages
        'sh': 'cURL',
        'python': 'Python',
        'js': 'JavaScript',
        // clients
    }

    const ICONS: Record<string, typeof IconInferenceBlackForest> = {
        // inference providers
        'black-forest-labs': IconInferenceBlackForest,
        'cerebras': IconInferenceCerebras,
        'cohere': IconInferenceCohere,
        'fal-ai': IconInferenceFal,
        'fireworks-ai': IconInferenceFireworks,
        'hf-inference': IconInferenceHf,
        'hyperbolic': IconInferenceHyperbolic,
        'nebius': IconInferenceNebius,
        'novita': IconInferenceNovita,
        'replicate': IconInferenceReplicate,
        'sambanova': IconInferenceSambaNova,
        'together': IconInferenceTogetherAI,
        // languages
        'sh': IconCurl,
        'python': IconPython,
        'js': IconJs,
        // clients
    }

    const base64 = (val: string) => btoa(encodeURIComponent(val));
</script>

<div class="flex gap-x-2 text-sm not-prose flex-col md:flex-row">
        <!-- Language selection -->
        {#if languages.length > 1}
            <div>
                <p class="font-mono text-sm opacity-50 sm:hidden md:block">Language</p>
                <div class="my-1.5 flex items-center gap-x-1 gap-y-0.5 flex-wrap">
                    {#each languages as language}
                            <button
                                class="text-md flex select-none items-center rounded-lg border px-1.5 py-1 leading-none
                                {selectedLanguage === language
                                    ? 'border-gray-800 bg-black text-white'
                                    : 'hover:shadow-xs cursor-pointer text-gray-500 opacity-90 hover:text-gray-700'}"
                                type="button"
                                on:click={() => selectedLanguage = language}
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
                <p class="font-mono text-sm opacity-50 sm:hidden md:block">Client</p>
                <div class="my-1.5 flex items-center gap-x-1 gap-y-0.5 flex-wrap">
                    {#each clients as client}
                            <button
                                class="text-md flex select-none items-center rounded-lg border px-1.5 py-1 leading-none
                                {selectedClient === client
                                    ? 'border-gray-800 bg-black text-white'
                                    : 'hover:shadow-xs cursor-pointer text-gray-500 opacity-90 hover:text-gray-700'}"
                                type="button"
                                on:click={() => selectedClient = client}
                            >
                                {client}
                            </button>
                    {/each}
                </div>
            </div>
        {/if}
    
        <!-- Stream checkbox (unchanged) -->
        {#if model.tags.includes("conversational")}
            <div>
                <p class="font-mono text-sm opacity-50 sm:hidden md:block">Stream</p>
                <div class="text-md group relative mb-2 flex items-center self-start leading-tight">
                    <span class="mr-1 sm:block md:hidden">stream:</span>
                    <input
                        class="my-2.5"
                        type="checkbox"
                        bind:checked={streaming}
                    />
                </div>
            </div>
        {/if}

        <!-- Provider selection -->
        {#if providers.length > 0}
        <div class="md:ml-auto">
            <p class="font-mono text-sm opacity-50 sm:hidden md:block">Provider</p>
            <div class="my-1.5 flex items-center gap-x-1 gap-y-0.5 flex-wrap">
                {#each providers as provider}
                        <button
                            class="text-md flex select-none items-center rounded-lg border px-1.5 py-1 leading-none
                            {selectedProvider === provider
                                ? 'border-gray-800 bg-black text-white'
                                : 'hover:shadow-xs cursor-pointer text-gray-500 opacity-90 hover:text-gray-700'}"
                            type="button"
                            on:click={() => selectedProvider = provider}
                        >
                            {#if ICONS[provider]}
                                <svelte:component this={ICONS[provider]} classNames="mr-1.5 text-current" />
                            {/if}
                            {PRETTY_NAMES[provider] ?? provider}
                        </button>
                {/each}
            </div>
        </div>
    {/if}
</div>

{#if code}
     <CodeBlock 
        code={base64(code)}
         highlighted={hljs.highlight(selectedLanguage, code, true).value}
      />
{/if}
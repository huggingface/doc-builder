# InferenceSnippet Component

The `InferenceSnippet` component is used to render an interactive interface for AI model inference. It uses [huggingface/huggingface.js](https://github.com/huggingface/huggingface.js) under the hood to get the snippets.

## Props

Below is a description of the props that can be passed to this component:

- **pipeline** (string, required):  
  Specifies the type of pipeline to be used for inference. Common values include `"text-generation"`, `"text-classification"`, etc.

- **providersMapping** (mapping of {modelId: string, providerModelId: string}, required):  
  A mapping which keys are provider names and values are objects with `modelId` and `providerModelId`.
  Example: `{"fireworks-ai": {modelId: "deepseek-ai/DeepSeek-R1", providerModelId: "accounts/fireworks/models/deepseek-r1", novita: {modelId: "deepseek-ai/DeepSeek-V3-0324", providerModelId: "deepseek/deepseek-v3-0324"}}`

- **conversational** (boolean, optional):  
  If set to `true`, the component will enable conversational mode, allowing for multi-turn interactions for `text-generation` models.

#### Example Usage

```svelte
<InferenceSnippet
	pipeline="text-generation"
	conversational
	providersMapping={{
    "fireworks-ai": {modelId: "deepseek-ai/DeepSeek-R1", providerModelId: "accounts/fireworks/models/deepseek-r1"},
    novita: {modelId: "deepseek-ai/DeepSeek-V3-0324", providerModelId: "deepseek/deepseek-v3-0324"}
  }}
/>
```

```svelte
<InferenceSnippet
	pipeline="text-generation"
	conversational
	providers={{
    "fireworks-ai": {modelId: "deepseek-ai/DeepSeek-R1", providerModelId: "accounts/fireworks/models/deepseek-r1"}
  }}
/>
```

```svelte
<InferenceSnippet
	pipeline="text-to-image"
	providers={{
    "black-forest-labs": {modelId: "black-forest-labs/FLUX.1-dev", providerModelId: "flux-dev"},
    "replicate": {modelId: "black-forest-labs/FLUX.1-dev", providerModelId: "black-forest-labs/flux-dev"},
    "fal-ai": {modelId: "black-forest-labs/FLUX.1-dev", providerModelId: "fal-ai/flux/dev"},
  }}
/>
```

## Adding new inference provider

Step 1: get latest `huggingface/huggingface.js` by running the command below:

```
cd kit
npm run update-inference-providers
```

Step 2: add an icon for the new provider in `kit/src/lib/InferenceSnippet/InferenceSnippet.svelte`.

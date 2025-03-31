# InferenceSnippet Component

The `InferenceSnippet` component is used to render an interactive interface for AI model inference. It uses [huggingface/huggingface.js](https://github.com/huggingface/huggingface.js) under the hood to get the snippets.

## Props

Below is a description of the props that can be passed to this component:

- **modelId** (string, required):  
  The identifier of the AI model to be used for inference. This should be a valid model ID, such as `"deepseek-ai/DeepSeek-R1"`.

- **pipeline** (string, required):  
  Specifies the type of pipeline to be used for inference. Common values include `"text-generation"`, `"text-classification"`, etc.

- **conversational** (boolean, optional):  
  If set to `true`, the component will enable conversational mode, allowing for multi-turn interactions for `text-generation` models.

- **providers** (array of strings, required):  
  A list of provider names that support the specified model and pipeline. Example: `["fireworks-ai", "cerebras", "cohere", "hyperbolic"]`.

#### Example Usage

```svelte
<InferenceSnippet
	modelId="deepseek-ai/DeepSeek-R1"
	pipeline="text-generation"
	conversational
	providers={["fireworks-ai", "cerebras", "cohere", "hyperbolic"]}
/>
```

```svelte
<InferenceSnippet
	modelId="deepseek-ai/DeepSeek-R1"
	pipeline="text-generation"
	conversational
	providers={["fireworks-ai"]}
/>
```

```svelte
<InferenceSnippet
	modelId="black-forest-labs/FLUX.1-dev"
	pipeline="text-to-image"
	providers={["black-forest-labs", "replicate", "fal-ai"]}
/>
```

## Adding new inference provider

Step 1: get latest `huggingface/huggingface.js` by running the command below:

```
cd kit
npm run update-inference-providers
```

Step 2: add an icon for the new provider in `kit/src/lib/InferenceSnippet/InferenceSnippet.svelte`.

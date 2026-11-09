/** Live catalog of the Inference Providers router, shared by `QuickstartSnippet` and `RoutingSnippet` */

export interface RouterProvider {
	provider: string;
	status: string;
	context_length?: number;
	pricing?: { input: number; output: number };
	supports_tools?: boolean;
	throughput?: number;
}

export interface RouterModel {
	id: string;
	architecture?: { input_modalities?: string[] };
	providers: RouterProvider[];
}

let models: Promise<Map<string, RouterModel>> | undefined;

/** `GET /v1/models` allows any origin; resolves to an empty map if the router can't be reached */
export function routerModels(): Promise<Map<string, RouterModel>> {
	models ??= fetch("https://router.huggingface.co/v1/models")
		.then((r) => r.json())
		.then(({ data }: { data: RouterModel[] }) => new Map(data.map((m) => [m.id, m])))
		.catch(() => new Map());
	return models;
}

const PROVIDER_NAMES: Record<string, string> = {
	baseten: "Baseten",
	cerebras: "Cerebras",
	cohere: "Cohere",
	deepinfra: "DeepInfra",
	"featherless-ai": "Featherless AI",
	"fireworks-ai": "Fireworks",
	groq: "Groq",
	novita: "Novita",
	nscale: "Nscale",
	ovhcloud: "OVHcloud",
	publicai: "Public AI",
	scaleway: "Scaleway",
	together: "Together AI",
	"zai-org": "Z.ai",
};

export const providerName = (slug: string) => PROVIDER_NAMES[slug] ?? slug;

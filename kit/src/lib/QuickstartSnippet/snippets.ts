/** Code and setup steps shown by `QuickstartSnippet`, for each API format and coding agent */

export const TOKEN_URL =
	"https://huggingface.co/settings/tokens/new?ownUserPermissions=inference.serverless.write&tokenType=fineGrained";

const PROMPT = "Why is the sky blue?";

export type Surface = "api" | "claude-code" | "codex" | "opencode" | "pi" | "hermes";
export type Format = "chat" | "responses" | "messages" | "hf";
export type Lang = "python" | "typescript" | "curl";

/** `docs` is the page "Read docs" links to, relative to the docs root */
export const SURFACES: { id: Surface; label: string; docs?: string }[] = [
	{ id: "api", label: "API" },
	{ id: "claude-code", label: "Claude Code", docs: "integrations/claude-code" },
	{ id: "codex", label: "Codex", docs: "integrations/codex" },
	{ id: "opencode", label: "OpenCode", docs: "integrations/opencode" },
	{ id: "pi", label: "Pi", docs: "integrations/pi" },
	{ id: "hermes", label: "Hermes Agent", docs: "integrations/hermes-agent" },
];

export const FORMATS: { id: Format; label: string; docs: string }[] = [
	{ id: "chat", label: "Chat Completions", docs: "tasks/chat-completion" },
	{ id: "responses", label: "Responses", docs: "guides/responses-api" },
	{ id: "messages", label: "Messages", docs: "tasks/chat-completion" },
	{ id: "hf", label: "HF SDKs", docs: "tasks/chat-completion" },
];

/** `hl` is the highlight.js language */
export const LANGS: { id: Lang; label: string; hl: string }[] = [
	{ id: "python", label: "Python", hl: "python" },
	{ id: "typescript", label: "TypeScript", hl: "typescript" },
	{ id: "curl", label: "cURL", hl: "bash" },
];

export const INSTALL: Record<Format, Partial<Record<Lang, string>>> = {
	chat: { python: "pip install openai", typescript: "npm install openai" },
	responses: { python: "pip install openai", typescript: "npm install openai" },
	messages: { python: "pip install anthropic", typescript: "npm install @anthropic-ai/sdk" },
	hf: { python: "pip install huggingface_hub", typescript: "npm install @huggingface/inference" },
};

function curl(path: string, body: object): string {
	return `curl https://router.huggingface.co${path} \\
  -H "Authorization: Bearer $HF_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '${JSON.stringify(body, null, 2).replace(/\n/g, "\n  ")}'`;
}

/** The HF SDKs have no cURL snippet */
export const API_CODE: Record<Format, Partial<Record<Lang, (model: string) => string>>> = {
	chat: {
		python: (m) => `import os
from openai import OpenAI

client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=os.environ["HF_TOKEN"],
)

stream = client.chat.completions.create(
    model="${m}",
    messages=[{"role": "user", "content": "${PROMPT}"}],
    stream=True,
)
for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="")`,
		typescript: (m) => `import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "https://router.huggingface.co/v1",
  apiKey: process.env.HF_TOKEN,
});

const stream = await client.chat.completions.create({
  model: "${m}",
  messages: [{ role: "user", content: "${PROMPT}" }],
  stream: true,
});
for await (const chunk of stream) {
  process.stdout.write(chunk.choices[0]?.delta?.content ?? "");
}`,
		curl: (m) =>
			curl("/v1/chat/completions", {
				model: m,
				messages: [{ role: "user", content: PROMPT }],
				stream: true,
			}),
	},
	responses: {
		python: (m) => `import os
from openai import OpenAI

client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=os.environ["HF_TOKEN"],
)

response = client.responses.create(
    model="${m}",
    input="${PROMPT}",
)
print(response.output_text)`,
		typescript: (m) => `import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "https://router.huggingface.co/v1",
  apiKey: process.env.HF_TOKEN,
});

const response = await client.responses.create({
  model: "${m}",
  input: "${PROMPT}",
});
console.log(response.output_text);`,
		curl: (m) => curl("/v1/responses", { model: m, input: PROMPT }),
	},
	messages: {
		python: (m) => `import os
from anthropic import Anthropic

# auth_token sends "Authorization: Bearer", which the router expects
client = Anthropic(
    base_url="https://router.huggingface.co",
    auth_token=os.environ["HF_TOKEN"],
)

message = client.messages.create(
    model="${m}",
    max_tokens=1024,
    messages=[{"role": "user", "content": "${PROMPT}"}],
)
# Reasoning models put a "thinking" block before the text
print(next(block.text for block in message.content if block.type == "text"))`,
		typescript: (m) => `import Anthropic from "@anthropic-ai/sdk";

// authToken sends "Authorization: Bearer", which the router expects
const client = new Anthropic({
  baseURL: "https://router.huggingface.co",
  authToken: process.env.HF_TOKEN,
});

const message = await client.messages.create({
  model: "${m}",
  max_tokens: 1024,
  messages: [{ role: "user", content: "${PROMPT}" }],
});
// Reasoning models put a "thinking" block before the text
console.log(message.content.find(block => block.type === "text")?.text);`,
		curl: (m) =>
			curl("/v1/messages", {
				model: m,
				max_tokens: 1024,
				messages: [{ role: "user", content: PROMPT }],
			}),
	},
	hf: {
		python: (m) => `from huggingface_hub import InferenceClient

client = InferenceClient()  # reads HF_TOKEN, or your \`hf auth login\`

stream = client.chat.completions.create(
    model="${m}",
    messages=[{"role": "user", "content": "${PROMPT}"}],
    stream=True,
)
for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="")`,
		typescript: (m) => `import { InferenceClient } from "@huggingface/inference";

const client = new InferenceClient(process.env.HF_TOKEN);

for await (const chunk of client.chatCompletionStream({
  model: "${m}",
  messages: [{ role: "user", content: "${PROMPT}" }],
})) {
  process.stdout.write(chunk.choices[0]?.delta?.content ?? "");
}`,
	},
};

/** `text` uses Markdown's `code` and **bold**: it's also copied as is in the prompt for agents */
export interface Step {
	title: string;
	text?: string;
	link?: { href: string; label: string };
	code?: string;
	hl?: string;
}

const TOKEN_STEP: Step = {
	title: "Create a Hugging Face token",
	text: "It needs the **Make calls to Inference Providers** permission.",
	link: { href: TOKEN_URL, label: "Create a token" },
};

const envTokenStep = (agent: string): Step => ({
	title: "Add your token",
	text: `${agent} reads it from \`HF_TOKEN\`.`,
	code: `export HF_TOKEN="hf_..."`,
	hl: "bash",
});

/** Setup steps of each coding agent for model `m`, whose repo name is `label` */
export const AGENT_STEPS: Record<Exclude<Surface, "api">, (m: string, label: string) => Step[]> = {
	"claude-code": (m, label) => [
		TOKEN_STEP,
		{
			title: "Install Claude Code",
			code: "curl -fsSL https://claude.ai/install.sh | bash",
			hl: "bash",
		},
		{
			title: "Add your token",
			text: "Claude Code sends it as a Bearer token.",
			code: `export ANTHROPIC_AUTH_TOKEN="hf_..."`,
			hl: "bash",
		},
		{
			title: "Point Claude Code at Hugging Face",
			text: `Every model slot uses ${label}.`,
			code: `export ANTHROPIC_BASE_URL="https://router.huggingface.co"
export ANTHROPIC_DEFAULT_OPUS_MODEL="${m}"
export ANTHROPIC_DEFAULT_SONNET_MODEL="${m}"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="${m}"`,
			hl: "bash",
		},
		{ title: "Start Claude Code", code: "claude", hl: "bash" },
	],
	codex: (m, label) => [
		TOKEN_STEP,
		{ title: "Install Codex", code: "npm install -g @openai/codex", hl: "bash" },
		envTokenStep("Codex"),
		{
			title: "Add Hugging Face as a provider",
			text: "In `~/.codex/config.toml`.",
			code: `[model_providers.huggingface]
name = "Hugging Face"
base_url = "https://router.huggingface.co/v1"
env_key = "HF_TOKEN"
wire_api = "responses"`,
			hl: "ini",
		},
		{
			title: `Start Codex with ${label}`,
			code: `codex -c model_provider=huggingface -m ${m}`,
			hl: "bash",
		},
	],
	opencode: (m, label) => [
		TOKEN_STEP,
		{
			title: "Install OpenCode",
			code: "curl -fsSL https://opencode.ai/install | bash",
			hl: "bash",
		},
		envTokenStep("OpenCode"),
		{
			title: `Start OpenCode with ${label}`,
			code: `opencode --model huggingface/${m}`,
			hl: "bash",
		},
	],
	pi: (m) => [
		TOKEN_STEP,
		{ title: "Install Pi", code: "curl -fsSL https://pi.dev/install.sh | sh", hl: "bash" },
		envTokenStep("Pi"),
		{
			title: "Set Hugging Face as the default provider",
			text: "In `~/.pi/agent/settings.json`.",
			code: `{
  "defaultProvider": "huggingface",
  "defaultModel": "${m}"
}`,
			hl: "json",
		},
		{ title: "Start Pi", code: "pi", hl: "bash" },
	],
	hermes: (m, label) => [
		TOKEN_STEP,
		{
			title: "Install Hermes Agent",
			code: "curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash",
			hl: "bash",
		},
		{
			title: "Add your token",
			text: "Hermes reads `HF_TOKEN` from `~/.hermes/.env`.",
			code: `echo 'HF_TOKEN=hf_...' >> ~/.hermes/.env`,
			hl: "bash",
		},
		{
			title: `Start Hermes with ${label}`,
			code: `hermes chat --provider hf --model ${m}`,
			hl: "bash",
		},
	],
};

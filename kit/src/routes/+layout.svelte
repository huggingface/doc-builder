
<script lang="ts">
	import { base } from "$app/paths";
	import { beforeNavigate, goto, onNavigate } from '$app/navigation';
	import type { RawChapter } from "./endpoints/toc/+server";
	import "../app.css";

	export let data;
	export let toc: RawChapter[] = data.toc ?? [];

	const library = import.meta.env.DOCS_LIBRARY || 'transformers';
	const version = import.meta.env.DOCS_VERSION || 'main';
	const lang = import.meta.env.DOCS_LANGUAGE || 'en';

	const redirectedPaths: Record<string, string> = {}

	beforeNavigate(async ({ to, cancel }) => {
		const pathname = to?.url.pathname ?? "";
		const search = to?.url.search ?? "";
		const hash = to?.url.hash ?? "";
		const path = pathname + search + hash;
		if(/^\/(docs|learn)/.test(path)){
			const params = path.slice(1).split("/");
			const _docType = params.shift();
			const _library = params.shift();
			const isCourse = _docType === "learn";
			const versionRegex = isCourse ? /^(?:pr_\d+)$/ : /^(?:(master|main)|v[\d.]+(rc\d+)?|pr_\d+)$/;
			const _version = versionRegex.test(params[0]) ? params.shift() : undefined;
			const _lang = /^[a-z]{2}(-[A-Z]{2})?$/.test(params[0]) ? params.shift() : undefined;
			const newChapterId = params.join("/");

			if (library === _library && (!_version || !_lang)){
				cancel();
				const redirectedPath = `/docs/${library}/${version}/${lang}/${newChapterId}`;
				redirectedPaths[redirectedPath] = path;
				await goto(redirectedPath);
				return false;
			}
		}
	});

	onNavigate(({ to }) => {
		const pathname = to?.url.pathname ?? "";
		const search = to?.url.search ?? "";
		const hash = to?.url.hash ?? "";
		const path = pathname + search + hash;
		if(redirectedPaths[path]){
			history.replaceState({}, "", redirectedPaths[path])
		}
	});
</script>

{#if !import.meta.env.DEV}
	<slot />
{:else}
	<style>
		body,
		html {
			padding: 0;
			margin: 0;
		}
	</style>
	<div
		class="flex"
	>
		<div class="w-[270px] 2xl:w-[300px] hidden md:block border-r-2 shrink-0">
			<ul class="pt-2 flex flex-col pl-3 w-full">
				{#each toc as section}
					{#if section.local}
						<a
							role="navigation"
							class="block text-gray-500 pr-2 hover:text-black dark:hover:text-gray-300 py-1"
							href="{base}/{section.local.replace(/\bindex$/, '')}">{section.title}</a
						>
					{:else}
						<span
						role="navigation"
						class="opacity-50 text-lg block text-gray-500 pr-2 hover:text-black dark:hover:text-gray-300 py-1"
						>{section.title}</span>
					{/if}
				{/each}
			</ul>
		</div>
		<div class="px-4 pt-3 grow">
			<div class="prose prose-doc dark:prose-light max-w-4xl mx-auto break-words relative">
				<slot />
			</div>
		</div>
		<div class="w-[270px] 2xl:w-[305px] hidden lg:block border-l-2 shrink-0 opacity-50 p-4">
			Sub side menu
		</div>
	</div>
{/if}

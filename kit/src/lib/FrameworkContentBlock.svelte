<script lang="ts">
    import type { SvelteComponent } from "svelte";
    import type { Framework } from "./types";

    import { onMount} from "svelte";
    import { getFrameworkStore } from "./stores";
	import IconPytorch from "./IconPytorch.svelte";
	import IconTensorflow from "./IconTensorflow.svelte";
	import IconJax from "./IconJax.svelte";
	import IconEyeShow from "./IconEyeShow.svelte";
	import IconEyeHide from "./IconEyeHide.svelte";

    export let framework: Framework;

    const FRAMEWORK_CONFIG: Record<Framework, {Icon: typeof SvelteComponent, label: string}> = {
		"pytorch": {
            Icon: IconPytorch,
            label: "Pytorch",
        },
		"tensorflow": {
            Icon: IconTensorflow,
            label: "TensorFlow",
        },
		"jax": {
            Icon: IconJax,
            label: "JAX",
        },
	};
    const { Icon, label } = FRAMEWORK_CONFIG[framework];
    const localStorageKey = `hf_doc_framework_${framework}_is_hidden`;
    const frameworkStore = getFrameworkStore(framework);

    function toggleHidden(){
        $frameworkStore = !$frameworkStore;
        localStorage.setItem(localStorageKey, $frameworkStore ? "true" : "false");
    }

    onMount(() => {
        if(localStorage.getItem(localStorageKey) === "true"){
            $frameworkStore = true;
        }
    })
</script>

<div
    class="framework-content border-2 border-gray-200 rounded-xl px-4 relative"
>
    <div
        class="absolute top-0 left-0 -translate-y-4 translate-x-4 flex items-center space-x-1 px-2 bg-white dark:bg-gray-950"
    >
        <svelte:component this={Icon} />
        <span>{label}</span>
    </div>
    <div
        class="absolute top-0 right-0 -translate-y-6 -translate-x-4 flex items-center space-x-1 px-2 bg-white dark:bg-gray-950"
    >
    {#if !$frameworkStore}
        <div class="cursor-pointer flex items-center justify-center space-x-1 py-2.5"
            on:click={toggleHidden}
        >
            <IconEyeHide/>
            <span>Hide {label} content</span>
        </div>
    {/if}
    </div>
    {#if $frameworkStore}
        <div class="cursor-pointer flex items-center justify-center space-x-1 py-2.5"
            on:click={toggleHidden}
        >
            <IconEyeShow/>
            <span>Show {label} content</span>
        </div>
    {:else}
        <slot />
    {/if}
</div>
	
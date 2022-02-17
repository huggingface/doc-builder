<script context="module" lang="ts">
  import { base } from "$app/paths";

  export async function load(input: LoadInput) {
    if (prerendering) {
      return {}
    }
  
    const language = /\/([a-z]{2})(\/|$)/.exec(input.url.toString())[1];

    const toc = await input.fetch(base + '/endpoints/toc?lang='+language)

    return {
      props: {
        toc: await toc.json(),
        language
      }
    }
  }
</script>

<script lang="ts">
  import type { LoadInput } from "@sveltejs/kit";
  import { prerendering } from "$app/env";

  export let toc: Array<{sections: Array<{title: string} & ({local: string} | {sections: {title: string, local: string}[]})>, title: string}>
  export let language: string
</script>

{#if prerendering}
  
  <slot>

  </slot>
  
{:else}
  <style>
    body, html {padding: 0; margin: 0;}
  </style>
  <div style="width: 100vh; height: 100vh; margin: 0; padding: 0; display: flex; flex-direction: row">
    <aside style="width: 270px; min-width: 270px; max-width: 270px; border-right: 1px solid gray; height: 100vh; position: fixed; overflow-y: auto; display: flex; flex-direction: column">
      <ul style="padding-left: 16px ; display: flex; flex-direction: column">
        {#each toc as section}
        <h3>{section.title}</h3>
        {#each section.sections as subsection}
          {#if "sections" in subsection}
            <h3>{subsection.title}</h3>

            <ul style="padding-left: 16px; display: flex; flex-direction: column">
              {#each subsection.sections as finalsection}
                <a role="navigation" href="{base}/{language}/{finalsection.local}">{finalsection.title}</a>
              {/each}
            </ul>
          {:else}
          <a role="navigation" href="{base}/{language}/{subsection.local}">{subsection.title}</a>
          {/if}
        {/each}
      {/each}
      </ul>
      
    </aside>
    <div style="padding-left: 16px; padding-right: 16px; margin-left: 270px">
      <slot>

      </slot>
    </div>
  </div>
{/if}